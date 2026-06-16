# Service Management — Technical Specification

## 1. Overview

The existing `admin_services` view (`core/views.py:1090`) manages ServiceVariant-based pricing, AddonServices, Services, and ServiceVariants. Gaps: **no edit operations** for any model, **no dynamic attribute fields** per service type, **no structured category management** beyond a hardcoded enum, and **no image upload** for services.

This document specifies the changes needed to close these gaps.

---

## 2. Architecture Alignment

All changes follow the project's existing conventions:

| Convention | Current Pattern |
|---|---|
| App structure | Single `core` app; no multi-app split |
| Template location | `templates/admin/` (centralized, not in app dirs) |
| View pattern | Function-based views with `@permission_required` |
| POST dispatch | `action = request.POST.get('action')` + `if/elif` branches |
| Permission roles | `user.is_readonly_staff`, `user.is_full_admin`, `@permission_required('manage_pricing')` |
| Model base class | All models extend `DualWriteMixin` |
| Timestamp fields | `created_at` / `updated_at` on mutable models |
| Active toggle | `is_active = models.BooleanField(default=True)` |
| Audit trail | `log_audit()` after mutations (from `core.audit_helpers`) |
| Cache | `cache.clear()` after pricing changes |
| Messages | `messages.success/error()` for feedback |
| Database | PostgreSQL via Supabase; all models force `using='default'` via `DualWriteMixin` |

---

## 3. Database Schema Changes

### 3.1 New Model: `ServiceAttribute` (`core/models.py`)

Stores **one key-value pair** per service type. Uses a JSON `value` field so each service type can define its own schema without migration churn.

```python
class ServiceAttribute(DualWriteMixin, models.Model):
    """Dynamic attribute fields for a service."""
    service = models.ForeignKey(
        Service, on_delete=models.CASCADE,
        related_name='attributes'
    )
    key = models.CharField(max_length=100)        # e.g. "page_qty", "gsm", "size", "dimension", "material"
    value = models.JSONField(default=dict, blank=True)  # {"min": 1, "max": 1000} or "80" or "A4"
    display_label = models.CharField(max_length=100, blank=True)  # UI label override
    is_required = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'key']
        unique_together = ('service', 'key')

    def __str__(self):
        return f"{self.service.name} — {self.key}"
```

### 3.2 Migration

Generate via standard Django migration:

```bash
python manage.py makemigrations core --name service_attributes
python manage.py migrate
```

### 3.3 Existing Model Changes

Add `sort_order` to `Service` for manual category ordering:

```python
# In Service model
sort_order = models.PositiveSmallIntegerField(default=0, help_text="Display sequence within category")
```

Update `Meta.ordering`:

```python
class Meta:
    ordering = ['category', 'sort_order', 'name']
```

Run a second migration: `python manage.py makemigrations core --name service_sort_order`

---

## 4. Backend Logic (`core/views.py`)

Extend the existing `admin_services` view (currently at line 1090) with new action branches. **Do not create a new view** — extend the existing one to preserve URL compatibility.

### 4.1 New POST Actions

All branches follow the existing pattern: check role, get object, mutate, `log_audit()`, `messages.success()`, `redirect('admin_services')`.

```python
# Inside admin_services() POST block, BEFORE the final redirect

elif action == 'update_service' and can_manage_addons:
    service = get_object_or_404(Service, pk=request.POST['service_id'])
    service.name = request.POST['name']
    service.category = request.POST.get('category', service.category)
    service.price = Decimal(request.POST['price'])
    service.description = request.POST.get('description', '')
    if request.FILES.get('image'):
        service.image = request.FILES['image']
    old_vals = {'name': old_name}
    service.save()
    log_audit(request.user, 'UPDATE', 'Service', service.pk, old_vals, {'name': service.name})

elif action == 'update_variant' and can_manage_addons:
    variant = get_object_or_404(ServiceVariant, pk=request.POST['variant_id'])
    old_vals = {'name': variant.name, 'additional_price': str(variant.additional_price)}
    variant.name = request.POST['name']
    variant.additional_price = Decimal(request.POST.get('additional_price', '0'))
    specs_data = request.POST.get('specs')
    if specs_data is not None:
        try:
            variant.specs = json.loads(specs_data)
        except json.JSONDecodeError:
            messages.error(request, 'Invalid JSON for specs.')
            return redirect('admin_services')
    variant.save()
    log_audit(request.user, 'UPDATE', 'ServiceVariant', variant.pk, old_vals,
             {'name': variant.name, 'additional_price': str(variant.additional_price)})

elif action == 'add_attribute':
    service = get_object_or_404(Service, pk=request.POST['service_id'])
    ServiceAttribute.objects.create(
        service=service,
        key=request.POST['key'],
        value=request.POST.get('value', {}),
        display_label=request.POST.get('display_label', ''),
        is_required=bool(request.POST.get('is_required')),
        sort_order=int(request.POST.get('sort_order', 0)),
    )
    messages.success(request, 'Attribute added.')

elif action == 'update_attribute':
    attr = get_object_or_404(ServiceAttribute, pk=request.POST['attribute_id'])
    old_vals = {'key': attr.key, 'value': attr.value}
    attr.key = request.POST['key']
    attr.value = request.POST.get('value', attr.value)
    attr.display_label = request.POST.get('display_label', attr.display_label)
    attr.is_required = bool(request.POST.get('is_required'))
    attr.sort_order = int(request.POST.get('sort_order', attr.sort_order))
    attr.save()
    log_audit(request.user, 'UPDATE', 'ServiceAttribute', attr.pk, old_vals,
             {'key': attr.key})

elif action == 'delete_attribute':
    attr = get_object_or_404(ServiceAttribute, pk=request.POST['attribute_id'])
    attr.delete()
    messages.success(request, 'Attribute deleted.')
```

### 4.2 Attribute Presets by Category

A **design-time mapping** (stored in a helper, not a DB table) provides sensible defaults per category:

```python
# core/service_helpers.py (new file)
ATTRIBUTE_PRESETS = {
    'Printing': [
        {'key': 'page_qty_min', 'display_label': 'Min Pages', 'is_required': False, 'sort_order': 0},
        {'key': 'page_qty_max', 'display_label': 'Max Pages', 'is_required': False, 'sort_order': 1},
        {'key': 'gsm',          'display_label': 'GSM Options', 'is_required': False, 'sort_order': 2},
        {'key': 'size',         'display_label': 'Paper Sizes', 'is_required': True,  'sort_order': 3},
    ],
    'Photo': [
        {'key': 'dimension',   'display_label': 'Dimensions (WxH)', 'is_required': True,  'sort_order': 0},
        {'key': 'material',    'display_label': 'Material', 'is_required': True,  'sort_order': 1},
        {'key': 'finish',      'display_label': 'Finish Type', 'is_required': False, 'sort_order': 2},
    ],
    'Stationery': [
        {'key': 'paper_type',  'display_label': 'Paper Type', 'is_required': True,  'sort_order': 0},
        {'key': 'size',        'display_label': 'Size', 'is_required': True,  'sort_order': 1},
        {'key': 'gsm',         'display_label': 'GSM', 'is_required': False, 'sort_order': 2},
    ],
    'Binding': [
        {'key': 'binding_type','display_label': 'Binding Type', 'is_required': True,  'sort_order': 0},
        {'key': 'page_range',  'display_label': 'Page Range', 'is_required': False, 'sort_order': 1},
    ],
    'Lamination': [
        {'key': 'lamination_type', 'display_label': 'Type', 'is_required': True,  'sort_order': 0},
        {'key': 'thickness',       'display_label': 'Thickness (mic)', 'is_required': False, 'sort_order': 1},
    ],
}
```

### 4.3 URL Routing

No new URLs required. The existing `/admin/services/` endpoint handles all actions.

---

## 5. Frontend UI (`templates/admin/services.html`)

### 5.1 Current Structure (to preserve)

The template has three sections:
1. **Print pricing rules** — per-page A4 grid (untouched)
2. **Add-on services** — card grid with toggle/delete/add (untouched)
3. **Services** — categorized card grid with variant sub-tables

### 5.2 Changes to the Services Section

#### A. Edit Service Form (replaces hardcoded "Create New Service" at bottom)

Replace the inline create form with an **edit panel per card**:

```html
<!-- Per-service card header: name, price, edit/delete buttons -->
<div class="p-4 rounded-lg border border-surface-border">
    <div class="flex items-center justify-between mb-3">
        <input type="text" name="service_name_{{ service.pk }}"
               value="{{ service.name }}" class="font-bold text-lg bg-transparent border-b border-transparent
              hover:border-surface-border focus:border-primary outline-none" />

        <span class="text-primary font-bold">Base: ৳{{ service.price|floatformat:0 }}</span>
    </div>

    <!-- Collapsible edit form (hidden by default, toggled via JS) -->
    <div id="edit-service-{{ service.pk }}" class="hidden">
        <form method="post" class="flex flex-col gap-3 mb-4 bg-surface p-4 rounded-lg">
            {% csrf_token %}
            <input type="hidden" name="action" value="update_service">
            <input type="hidden" name="service_id" value="{{ service.pk }}">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <input type="text" name="name" value="{{ service.name }}" required class="form-input">
                <select name="category" class="form-select">
                    {% for val, label in service.CATEGORY_CHOICES %}
                    <option value="{{ val }}" {% if service.category == val %}selected{% endif %}>{{ label }}</option>
                    {% endfor %}
                </select>
                <input type="number" name="price" value="{{ service.price }}" step="0.01" required class="form-input">
                <input type="file" name="image" accept="image/*" class="form-input">
                {% if service.image %}
                <div class="sm:col-span-2">
                    <img src="{{ service.image.url }}" class="h-16 rounded object-cover" alt="{{ service.name }}">
                    <label class="flex items-center gap-2 text-xs text-text-muted mt-1">
                        <input type="checkbox" name="remove_image"> Remove image
                    </label>
                </div>
                {% endif %}
            </div>
            <textarea name="description" rows="2" class="form-input">{{ service.description }}</textarea>
            <div class="flex gap-2">
                <button type="submit" class="btn-primary text-sm">Save Changes</button>
                <button type="button" onclick="toggleEdit('edit-service-{{ service.pk }}')"
                        class="btn-secondary text-sm">Cancel</button>
            </div>
        </form>
    </div>

    <button onclick="toggleEdit('edit-service-{{ service.pk }}')" class="text-xs text-primary mb-3">
        <i class="bi bi-pencil"></i> Edit
    </button>
</div>
```

#### B. Dynamic Attribute Fields (per service card)

After the variants table, add the attributes section:

```html
<!-- Service Attributes Section -->
<div class="mt-4 border-t border-surface-border pt-4">
    <h4 class="text-sm font-semibold mb-3 flex items-center gap-2">
        <i class="bi bi-sliders2 text-primary"></i> Service Fields
    </h4>

    {% if service.attributes.all %}
    <div class="space-y-2 mb-4">
        {% for attr in service.attributes.all %}
        <form method="post" class="flex flex-wrap items-center gap-2 bg-surface p-2 rounded">
            {% csrf_token %}
            <input type="hidden" name="action" value="update_attribute">
            <input type="hidden" name="attribute_id" value="{{ attr.pk }}">
            <input type="text" name="key" value="{{ attr.key }}"
                   class="form-input text-xs w-28" placeholder="key">
            <input type="text" name="display_label" value="{{ attr.display_label|default:attr.key }}"
                   class="form-input text-xs flex-1" placeholder="Label">
            <input type="text" name="value" value="{{ attr.value|json_script:'' }}"
                   class="form-input text-xs w-24" placeholder="Value">
            <label class="flex items-center gap-1 text-xs">
                <input type="checkbox" name="is_required" {% if attr.is_required %}checked{% endif %}>
                Required
            </label>
            <input type="number" name="sort_order" value="{{ attr.sort_order }}"
                   class="form-input text-xs w-12" placeholder="Order">
            <button type="submit" class="btn-primary text-xs h-8 px-2"><i class="bi bi-check"></i></button>
            <button type="submit" name="action" value="delete_attribute" onclick="return confirm('Delete?')"
                    class="text-red-400 text-xs h-8"><i class="bi bi-trash"></i></button>
        </form>
        {% endfor %}
    </div>
    {% endif %}

    <!-- Add Attribute Form -->
    <form method="post" class="flex flex-wrap items-center gap-2 bg-surface/50 p-3 rounded-lg">
        {% csrf_token %}
        <input type="hidden" name="action" value="add_attribute">
        <input type="hidden" name="service_id" value="{{ service.pk }}">
        <input type="text" name="key" required placeholder="field_key" class="form-input text-xs w-28">
        <input type="text" name="display_label" placeholder="Display Label" class="form-input text-xs flex-1">
        <input type="text" name="value" placeholder='{"unit":"pcs"}' class="form-input text-xs w-36">
        <label class="flex items-center gap-1 text-xs">
            <input type="checkbox" name="is_required"> Req
        </label>
        <input type="number" name="sort_order" value="0" class="form-input text-xs w-12">
        <button type="submit" class="btn-primary text-xs"><i class="bi bi-plus"></i> Add Field</button>
    </form>

    <!-- Quick preset buttons based on category -->
    {% with presets=service.ATTRIBUTE_PRESETS|default:service.attributes.all %}
    {% if service.category == 'Printing' or service.category == 'Stationery' %}
    <div class="mt-2 flex flex-wrap gap-2">
        <span class="text-xs text-text-muted">Quick add:</span>
        {% for preset in ATTRIBUTE_PRESETS|get_item:service.category %}
        <form method="post" class="inline">
            {% csrf_token %}
            <input type="hidden" name="action" value="add_attribute">
            <input type="hidden" name="service_id" value="{{ service.pk }}">
            <input type="hidden" name="key" value="{{ preset.key }}">
            <input type="hidden" name="display_label" value="{{ preset.display_label }}">
            <input type="hidden" name="is_required" value="{{ preset.is_required|yesno:'1,0' }}">
            <input type="hidden" name="sort_order" value="{{ preset.sort_order }}">
            <button type="submit" class="text-xs border border-surface-border rounded px-2 py-1 hover:border-primary">
                <i class="bi bi-plus-circle"></i> {{ preset.display_label }}
            </button>
        </form>
        {% endfor %}
    </div>
    {% endif %}
    {% endwith %}
</div>
```

#### C. Template Filter for `get_item` dictionary access

Add to `core/templatetags/service_extras.py`:

```python
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)
```

### 5.3 Variant Edit Enhancement

Add a small edit form next to each variant row in the existing table. Replace inline action buttons:

```html
<tr id="variant-row-{{ variant.pk }}">
    <td class="py-1">
        <span id="v-name-{{ variant.pk }}">{{ variant.name }}</span>
        <input type="hidden" id="v-edit-{{ variant.pk }}" value="0">
    </td>
    <td class="py-1"><span id="v-price-{{ variant.pk }}">+৳{{ variant.additional_price|floatformat:0 }}</span></td>
    <td class="py-1">{% if variant.inventory_item %}{{ variant.inventory_item.current_stock|floatformat:0 }}{% else %}-{% endif %}</td>
    <td class="py-1">
        <a href="#" onclick="showVariantEdit({{ variant.pk }})" class="text-primary"><i class="bi bi-pencil"></i></a>
        <span class="mx-1">|</span>
        <form method="post" class="inline" onsubmit="return confirm('Delete variant?')">
            {% csrf_token %}
            <input type="hidden" name="action" value="delete_variant">
            <input type="hidden" name="variant_id" value="{{ variant.pk }}">
            <button type="submit" class="text-red-400"><i class="bi bi-trash"></i></button>
        </form>
    </td>
</tr>
<tr id="variant-edit-{{ variant.pk }}" class="hidden bg-surface/50">
    <td colspan="4" class="p-2">
        <form method="post" class="flex flex-wrap items-center gap-2">
            {% csrf_token %}
            <input type="hidden" name="action" value="update_variant">
            <input type="hidden" name="variant_id" value="{{ variant.pk }}">
            <input type="text" name="name" value="{{ variant.name }}" required class="form-input text-xs">
            <input type="number" name="additional_price" value="{{ variant.additional_price }}" step="0.01" class="form-input text-xs w-24">
            <textarea name="specs" class="form-input text-xs" rows="1" placeholder='{"gsm": "80"}'>{{ variant.specs|safe }}</textarea>
            <button type="submit" class="btn-primary text-xs">Save</button>
            <button type="button" onclick="hideVariantEdit({{ variant.pk }})" class="btn-secondary text-xs">Cancel</button>
        </form>
    </td>
</tr>
```

---

## 6. JavaScript Toggles (`templates/admin_base.html` footer block)

Add these utility functions once in the admin base template's existing `<script>` block:

```javascript
function toggleEdit(elementId) {
    const el = document.getElementById(elementId);
    el.classList.toggle('hidden');
}
function showVariantEdit(variantId) {
    document.getElementById('variant-edit-' + variantId).classList.remove('hidden');
    document.getElementById('variant-row-' + variantId).classList.add('hidden');
}
function hideVariantEdit(variantId) {
    document.getElementById('variant-edit-' + variantId).classList.add('hidden');
    document.getElementById('variant-row-' + variantId).classList.remove('hidden');
}
```

---

## 7. Admin Registration Additions (`core/admin.py`)

Register `ServiceAttribute` for direct Django admin access (bypassing the custom view):

```python
from .models import ServiceAttribute, Service, ServiceVariant, AddonService, Coupon, Expense, SiteSettings, AuditLog, Notification, OrderStatusLog, EmailLog, EmailTemplate, User, WalkInCustomer, Order, OrderFile, OrderFilePageRange, InventoryItem, InventoryLog

@admin.register(ServiceAttribute)
class ServiceAttributeAdmin(admin.ModelAdmin):
    list_display = ['service', 'key', 'display_label', 'is_required', 'sort_order']
    list_filter = ['service__category', 'is_required']
    search_fields = ['key', 'display_label', 'service__name']
    ordering = ['service', 'sort_order']
```

Also register `Service` and `ServiceVariant` (currently not registered):

```python
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'description']

@admin.register(ServiceVariant)
class ServiceVariantAdmin(admin.ModelAdmin):
    list_display = ['service', 'name', 'additional_price', 'is_active']
    list_filter = ['service__category', 'is_active']
    search_fields = ['name', 'service__name']
```

---

## 8. API Endpoint for Dynamic Attribute Rendering (Optional)

If the public-facing `new_order` page needs to render attribute fields dynamically based on service selection, add:

```python
# core/views.py
def api_service_attributes(request, service_id):
    """Return attribute schema for a service's variants."""
    from .models import Service, ServiceAttribute
    service = get_object_or_404(Service, pk=service_id)
    attributes = list(service.attributes.values('key', 'display_label', 'value', 'is_required', 'sort_order'))
    variants = list(service.variants.filter(is_active=True).values('pk', 'name', 'additional_price', 'specs'))
    return JsonResponse({'attributes': attributes, 'variants': variants})
```

URL:

```python
# core/urls.py
path('api/services/<int:service_id>/attributes/', views.api_service_attributes, name='api_service_attributes'),
```

---

## 9. Migration & Deployment Checklist

### 9.1 File Changes Summary

| File | Change |
|---|---|
| `core/models.py` | Add `ServiceAttribute` model; add `sort_order` to `Service` |
| `core/views.py` | Extend `admin_services()` with update/edit/attribute actions |
| `core/templatetags/service_extras.py` | New file — `get_item` filter |
| `core/service_helpers.py` | New file — `ATTRIBUTE_PRESETS` mapping |
| `core/admin.py` | Register `Service`, `ServiceVariant`, `ServiceAttribute` |
| `core/urls.py` | Add optional `api_service_attributes` URL |
| `templates/admin/services.html` | Full rewrite of service card section with edit forms and attribute fields |
| `templates/admin_base.html` | Add JS toggle functions |

### 9.2 Commands

```bash
# 1. Create migrations
python manage.py makemigrations core --name add_service_attributes
python manage.py makemigrations core --name service_sort_order

# 2. Validate schema
python manage.py sqlmigrate core 0030   # (check next migration number)

# 3. Apply
python manage.py migrate

# 4. Quality checks (from AGENTS.md)
python -m py_compile core/models.py core/views.py core/service_helpers.py
python -m flake8 core/ --select=F821
mypy core\service_helpers.py --ignore-missing-imports
```

### 9.3 Permission Matrix

| Action | Allowed Roles |
|---|---|
| View services | `manage_pricing` permission (operator+) |
| Add/Edit/Toggle service | `manage_pricing` (operator+, manager+, admin+, super_admin) |
| Delete service/variant/attribute | `is_full_admin` (admin+, super_admin) |
| Edit AddonService price | `manage_pricing` |
| Delete AddonService | `is_full_admin` |

### 9.4 Backward Compatibility

- Existing `Service.specs` JSON field remains untouched on the model.
- `ServiceVariant` edits parse `specs` from a textarea to preserve JSON compatibility.
- `Service.category` choices remain the same enum; no data migration needed.
- The URL `/admin/services/` is unchanged.
- Public-facing `public_services` view is unaffected.

---

## 10. Testing Checklist

| Test | Steps |
|---|---|
| Create service with attributes | Post action=add_service, then action=add_attribute with preset key |
| Edit service | Toggle edit form, update name/price/category/image, submit |
| Delete service | Confirm removal; verify variants/attributes cascade-delete |
| Update variant | Click edit inline, change name/additional_price/specs JSON |
| Add attribute with preset | Click quick-add button for category preset |
| Search/filter admin | Use `/sys-admin/` Django admin on ServiceAttribute by category |
| Image upload | Upload via edit form; verify MEDIA path |
| Permission gate | Log in as viewer; confirm no edit buttons visible |
| Cache invalidation | After price change, verify `cache.clear()` is preserved |
| Audit trail | Verify `AuditLog` entries for create/update/delete |
| Attribute display order | Confirm `sort_order` controls attribute row order |

---

*Generated for PrintEdge project. Aligns with existing: single-app architecture, POST-action dispatch, `DualWriteMixin`, role-based permissions, centralized templates, Tailwind CSS styling.*
