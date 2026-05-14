from django.shortcuts import render

# Admin Views
def admin_dashboard(request):
    return render(request, 'admin/dashboard.html')

def admin_orders(request):
    mock_orders = [
        {'id':'PE-OFF-20260513-0028','customer':'Tariqul Islam','phone':'+8801700000001','specs':'B&W · Double · 24p · 3x','file':'thesis.pdf','amount':'৳504','paid':'Unpaid','source':'offline','status':'pending','urgent':True},
        {'id':'PE-ON-20260513-0027','customer':'Arif Ahmed','phone':'arif@example.com','specs':'Color · Single · 15p · 1x','file':'assignment.docx','amount':'৳150','paid':'bKash','source':'online','status':'printing','urgent':False},
        {'id':'PE-ON-20260513-0026','customer':'Sadia Rahman','phone':'sadia@univ.edu.bd','specs':'B&W · Single · 8p · 2x','file':'notes.pdf','amount':'৳32','paid':'Cash','source':'online','status':'ready','urgent':False},
        {'id':'PE-OFF-20260513-0025','customer':'Karim Uddin','phone':'+8801900000002','specs':'Color · Double · 30p · 1x','file':'(Physical)','amount':'৳450','paid':'Cash','source':'offline','status':'delivered','urgent':False}
    ]
    kanban_cols = [
        ('pending', 'Pending', 'warning'),
        ('printing', 'Printing', 'info'),
        ('ready', 'Ready', 'success'),
        ('delivered', 'Delivered', 'secondary'),
        ('cancelled', 'Cancelled', 'danger')
    ]
    return render(request, 'admin/orders.html', {'orders': mock_orders, 'kanban_cols': kanban_cols})

def admin_walkin_order(request):
    return render(request, 'admin/walkin_order.html')

def admin_users(request):
    return render(request, 'admin/users.html')

def admin_offline_customers(request):
    mock_customers = [
        {'id':'WC-0001','name':'Tariqul Islam','phone':'01700000001','tier':'Gold','orders':32,'total':'৳12,450','last':'Today'},
        {'id':'WC-0002','name':'Arif Ahmed','phone':'01800000002','tier':'Silver','orders':15,'total':'৳5,200','last':'2 days ago'},
        {'id':'WC-0003','name':'Sadia Rahman','phone':'01900000003','tier':'Bronze','orders':8,'total':'৳2,100','last':'1 week ago'}
    ]
    return render(request, 'admin/offline_customers.html', {'customers': mock_customers})

def admin_services(request):
    return render(request, 'admin/services.html')

def admin_inventory(request):
    mock_items = [
        {'id':'INV-001','name':'A4 Offset Paper','category':'Paper','stock':12500,'min':2000,'unit':'sheets','status':'In Stock','color':'success'},
        {'id':'INV-002','name':'A3 Glossy Paper','category':'Paper','stock':150,'min':200,'unit':'sheets','status':'Low Stock','color':'warning'},
        {'id':'INV-003','name':'Black Toner (HP)','category':'Ink','stock':4,'min':2,'unit':'pcs','status':'In Stock','color':'success'},
        {'id':'INV-004','name':'Color Toner (CMYK)','category':'Ink','stock':0,'min':1,'unit':'set','status':'Out of Stock','color':'danger'},
        {'id':'INV-005','name':'Spiral Coils (10mm)','category':'Binding','stock':85,'min':50,'unit':'pcs','status':'In Stock','color':'success'}
    ]
    return render(request, 'admin/inventory.html', {'items': mock_items})

def admin_financial(request):
    # Dummy placeholder for now, or real template if it exists
    return render(request, 'admin/financial.html')

def admin_staff(request):
    return render(request, 'admin/staff.html')

def admin_reports(request):
    return render(request, 'admin/reports.html')

def admin_audit_log(request):
    return render(request, 'admin/audit_log.html')

def admin_display_mode(request):
    return render(request, 'admin/display.html')

def admin_settings(request):
    return render(request, 'admin/settings.html')

# Auth Views
def auth_login(request):
    if request.method == 'POST':
        # Mock successful login
        return JsonResponse({'success': True, 'redirect': '/admin/dashboard/'})
    return render(request, 'auth/login.html')

def auth_register(request):
    if request.method == 'POST':
        # Mock successful registration
        return JsonResponse({'success': True, 'redirect': '/auth/login/'})
    return render(request, 'auth/register.html')

def auth_logout(request):
    from django.shortcuts import redirect
    return redirect('auth_login_page')

# User/Public Views
def public_index(request):
    return render(request, 'index.html')

def public_pricing(request):
    return render(request, 'pricing.html')

def user_dashboard(request):
    return render(request, 'user/dashboard.html')

# API Views
from django.http import JsonResponse
import json

def api_search(request):
    query = request.GET.get('q', '').lower()
    # Placeholder search logic — integrate with actual models later
    results = [
        {'title': 'Tariqul Islam', 'subtitle': 'Customer · 01700000001', 'url': '/admin/customers/offline/', 'icon': 'bi-person', 'type': 'customer'},
        {'title': 'Order PE-OFF-1234', 'subtitle': 'Status: Printing · ৳450', 'url': '/admin/orders/', 'icon': 'bi-cart', 'type': 'order'},
        {'title': 'A4 Offset Paper', 'subtitle': 'Stock: 1,200 sheets', 'url': '/admin/inventory/', 'icon': 'bi-box', 'type': 'inventory'},
    ]
    filtered = [r for r in results if query in r['title'].lower() or query in r['subtitle'].lower()]
    return JsonResponse({'results': filtered})

def api_order_status(request, order_id):
    if request.method == 'PATCH':
        try:
            data = json.loads(request.body)
            status = data.get('status')
            # Update order in DB here
            return JsonResponse({'success': True, 'order_id': order_id, 'new_status': status})
        except:
            return JsonResponse({'success': False}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)
