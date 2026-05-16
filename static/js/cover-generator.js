/**
 * Print Edge — Universal Assignment Cover Studio
 * Based on Assignment-Cover-Page by MeTariqul (MIT). Adapted for Print Edge.
 */
const A4_WIDTH_MM = 210;
const A4_HEIGHT_MM = 297;
const A4_WIDTH_PX = 794;
const A4_HEIGHT_PX = 1123;
const EXPORT_SCALE = 300 / 96;
const STORAGE_KEY = 'pe_cover_draft_v2';
const LOGO_CUSTOM_KEY = 'pe_cover_logo_custom';
const LOGO_MAX_BYTES = 500 * 1024;

const TEMPLATE_META = {
  classic: { label: 'Classic Centered', desc: 'Formal centered composition' },
  modern: { label: 'Modern Accent', desc: 'Sharp accents, left hierarchy' },
  framed: { label: 'Formal Framed', desc: 'Certificate-style frame' },
  elegant: { label: 'Elegant Serif', desc: 'Refined serif presentation' },
  edge: { label: 'Print Edge', desc: 'Indigo–purple brand gradient' },
  minimal: { label: 'Minimal Airy', desc: 'Large whitespace, thin rules' },
  academic: { label: 'Academic Seal', desc: 'Institutional seal and banner' },
  bold: { label: 'Bold Header', desc: 'Dark header, light cards' },
  sidebar: { label: 'Brand Sidebar', desc: 'Vertical brand strip layout' },
  ledger: { label: 'Ledger Table', desc: 'Zebra label rows' },
};

const COVER_TEMPLATES = Object.keys(TEMPLATE_META).map((id) => ({
  id,
  label: TEMPLATE_META[id].label,
  desc: TEMPLATE_META[id].desc,
}));

const LEGACY_TEMPLATE_MAP = {
  formal: 'classic',
  modern: 'modern',
  minimal: 'minimal',
  classic: 'framed',
  elegant: 'elegant',
  academic: 'academic',
  bold: 'bold',
  sidebar: 'sidebar',
  geometric: 'edge',
  ledger: 'ledger',
  split: 'sidebar',
  sunrise: 'classic',
  emerald: 'academic',
  coral: 'classic',
  royal: 'bold',
  aurora: 'edge',
  citrus: 'edge',
  ruby: 'classic',
  lagoon: 'ledger',
  solar: 'edge',
  rose: 'minimal',
  midnight: 'bold',
  tropical: 'edge',
  peach: 'minimal',
  oceanic: 'edge',
  festival: 'edge',
};

const DESIGNATION_OPTIONS = [
  'Lecturer',
  'Senior Lecturer',
  'Assistant Professor',
  'Associate Professor',
  'Professor',
];

const DRAFT_KEYS = [
  'template', 'university', 'department', 'sameDept', 'courseName', 'courseCode',
  'assignmentTitle', 'instructor', 'designation', 'teacherDept', 'studentName',
  'studentId', 'studentDept', 'section', 'semester', 'submissionDate', 'logoHidden',
];

function coverPageGenerator(defaults = {}) {
  const todayIso = new Date().toISOString().split('T')[0];

  return {
    template: 'classic',
    defaultLogoUrl: defaults.defaultLogoUrl || '',
    customLogoUrl: '',
    logoHidden: false,
    university: defaults.university || '',
    department: '',
    sameDept: true,
    courseName: '',
    courseCode: '',
    assignmentTitle: '',
    instructor: '',
    designation: '',
    teacherDept: '',
    studentName: '',
    studentId: '',
    studentDept: '',
    section: '',
    semester: '',
    submissionDate: '',
    exportBusy: false,

    templates: COVER_TEMPLATES,
    designationOptions: DESIGNATION_OPTIONS,

    init() {
      this.defaultLogoUrl = defaults.defaultLogoUrl || this.defaultLogoUrl;
      this.loadDraft();
      this.$watch('department', () => this.syncDepartmentFields());
      this.$watch('sameDept', () => this.syncDepartmentFields());
      this.$watch('template', () => this.saveDraft());
      [
        'university', 'department', 'courseName', 'courseCode', 'assignmentTitle',
        'instructor', 'designation', 'teacherDept', 'studentDept', 'studentName',
        'studentId', 'section', 'semester', 'submissionDate', 'customLogoUrl', 'logoHidden',
      ].forEach((key) => {
        this.$watch(key, () => this.saveDraft());
      });
    },

    filled(val) {
      return Boolean(String(val ?? '').trim());
    },

    get activeTemplateMeta() {
      return TEMPLATE_META[this.template] || TEMPLATE_META.classic;
    },

    get displayLogoUrl() {
      if (this.logoHidden) return '';
      return this.customLogoUrl || this.defaultLogoUrl || '';
    },

    get universityDisplay() {
      return this.filled(this.university) ? this.university.toUpperCase() : '';
    },

    get studentIdDisplay() {
      return this.filled(this.studentId) ? `ID: ${this.studentId}` : '';
    },

    get instructorDeptDisplay() {
      if (this.sameDept) return this.filled(this.department) ? this.department : '';
      return this.filled(this.teacherDept) ? this.teacherDept : '';
    },

    get studentDeptDisplay() {
      if (this.sameDept) return this.filled(this.department) ? this.department : '';
      return this.filled(this.studentDept) ? this.studentDept : '';
    },

    get dateDisplay() {
      if (!this.filled(this.submissionDate)) return '';
      const date = new Date(`${this.submissionDate}T00:00:00`);
      if (Number.isNaN(date.getTime())) return this.submissionDate;
      const day = String(date.getDate()).padStart(2, '0');
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const year = date.getFullYear();
      return `${day}/${month}/${year}`;
    },

    get sectionDisplay() {
      return this.filled(this.section) ? `Section: ${this.section}` : '';
    },

    get showUniversity() { return this.filled(this.university); },
    get showAssignmentTitle() { return this.filled(this.assignmentTitle); },
    get showCourseName() { return this.filled(this.courseName); },
    get showCourseCode() { return this.filled(this.courseCode); },
    get showDetailsSection() {
      return this.showAssignmentTitle || this.showCourseName || this.showCourseCode;
    },
    get showInstructor() { return this.filled(this.instructor); },
    get showDesignation() { return this.filled(this.designation); },
    get showTeacherDept() { return this.filled(this.instructorDeptDisplay); },
    get showSubmittedTo() {
      return this.showInstructor || this.showDesignation || this.showTeacherDept;
    },
    get showStudentName() { return this.filled(this.studentName); },
    get showStudentId() { return this.filled(this.studentId); },
    get showStudentDept() { return this.filled(this.studentDeptDisplay); },
    get showSemester() { return this.filled(this.semester); },
    get showSection() { return this.filled(this.section); },
    get showSubmittedBy() {
      return this.showStudentName || this.showStudentId || this.showStudentDept
        || this.showSemester || this.showSection;
    },
    get showFooterDate() { return this.filled(this.submissionDate); },
    get showAssignmentBanner() {
      return this.showDetailsSection || this.showSubmittedTo || this.showSubmittedBy;
    },

    get coverPageClass() {
      const parts = ['cover-page', `template-${this.template}`];
      if (!this.displayLogoUrl) parts.push('cover-no-logo');
      if (!this.showDetailsSection && !this.showSubmittedTo && !this.showSubmittedBy) {
        parts.push('cover-compact-mid');
      }
      if (!this.showSubmittedTo && !this.showSubmittedBy) parts.push('cover-no-info');
      return parts.join(' ');
    },

    normalizeTemplate(id) {
      if (TEMPLATE_META[id]) return id;
      if (LEGACY_TEMPLATE_MAP[id]) return LEGACY_TEMPLATE_MAP[id];
      return 'classic';
    },

    applyDraft(data) {
      if (!data || typeof data !== 'object') return;
      DRAFT_KEYS.forEach((key) => {
        if (Object.prototype.hasOwnProperty.call(data, key)) {
          let val = data[key];
          if (typeof val === 'string') val = val.trim();
          this[key] = val;
        }
      });
      if (data.template) this.template = this.normalizeTemplate(data.template);
    },

    syncDepartmentFields() {
      if (this.sameDept) {
        if (this.filled(this.department)) {
          this.teacherDept = this.department;
          this.studentDept = this.department;
        } else {
          this.teacherDept = '';
          this.studentDept = '';
        }
      }
    },

    loadDraft() {
      try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
          this.applyDraft(JSON.parse(saved));
        } else {
          this.migrateLegacyDraft();
        }
      } catch (_) { /* ignore */ }

      this.template = this.normalizeTemplate(this.template);

      try {
        const custom = sessionStorage.getItem(LOGO_CUSTOM_KEY);
        if (custom) this.customLogoUrl = custom;
      } catch (_) { /* ignore */ }

      if (this.logoHidden !== true) this.logoHidden = false;
      if (this.sameDept !== false) this.sameDept = true;
      this.syncDepartmentFields();
    },

    migrateLegacyDraft() {
      try {
        const legacy = localStorage.getItem('pe_cover_draft');
        if (!legacy) return;
        const data = JSON.parse(legacy);
        if (data.template) this.template = this.normalizeTemplate(data.template);
        if (data.university) this.university = data.university;
        if (data.department) this.department = data.department;
        if (data.courseName) this.courseName = data.courseName;
        if (data.courseCode) this.courseCode = data.courseCode;
        if (data.assignmentTitle) this.assignmentTitle = data.assignmentTitle;
        if (data.instructor) this.instructor = data.instructor;
        if (data.studentName) this.studentName = data.studentName;
        if (data.studentId) this.studentId = data.studentId;
        if (data.section) this.section = data.section;
        if (data.semester) this.semester = data.semester;
        if (data.date) {
          const parsed = Date.parse(data.date);
          if (!Number.isNaN(parsed)) {
            this.submissionDate = new Date(parsed).toISOString().split('T')[0];
          }
        }
        this.syncDepartmentFields();
      } catch (_) { /* ignore */ }
    },

    saveDraft() {
      const payload = {
        template: this.template,
        university: this.university,
        department: this.department,
        sameDept: this.sameDept,
        courseName: this.courseName,
        courseCode: this.courseCode,
        assignmentTitle: this.assignmentTitle,
        instructor: this.instructor,
        designation: this.designation,
        teacherDept: this.teacherDept,
        studentName: this.studentName,
        studentId: this.studentId,
        studentDept: this.studentDept,
        section: this.section,
        semester: this.semester,
        submissionDate: this.submissionDate,
        logoHidden: this.logoHidden,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    },

    reset() {
      localStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem(LOGO_CUSTOM_KEY);
      this.template = 'classic';
      this.university = '';
      this.department = '';
      this.sameDept = true;
      this.courseName = '';
      this.courseCode = '';
      this.assignmentTitle = '';
      this.instructor = '';
      this.designation = '';
      this.teacherDept = '';
      this.studentName = '';
      this.studentId = '';
      this.studentDept = '';
      this.section = '';
      this.semester = '';
      this.submissionDate = '';
      this.customLogoUrl = '';
      this.logoHidden = false;
    },

    async onLogoSelected(event) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      if (file.size > LOGO_MAX_BYTES) {
        alert('Logo must be under 500 KB.');
        event.target.value = '';
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        this.customLogoUrl = reader.result;
        this.logoHidden = false;
        try {
          sessionStorage.setItem(LOGO_CUSTOM_KEY, this.customLogoUrl);
        } catch (_) {
          alert('Logo is too large to save in the browser. It will work until you refresh.');
        }
        this.saveDraft();
      };
      reader.readAsDataURL(file);
    },

    hideLogo() {
      this.logoHidden = true;
      const input = document.getElementById('cover-logo-input');
      if (input) input.value = '';
      this.saveDraft();
    },

    resetLogoToDefault() {
      this.customLogoUrl = '';
      this.logoHidden = false;
      sessionStorage.removeItem(LOGO_CUSTOM_KEY);
      const input = document.getElementById('cover-logo-input');
      if (input) input.value = '';
      this.saveDraft();
    },

    get usesCustomLogo() {
      return Boolean(this.customLogoUrl);
    },

    validateForm() {
      return Boolean(document.getElementById('cover-page'));
    },

    getSafeFilename() {
      const base = this.filled(this.studentName) ? this.studentName : 'Assignment';
      return base.trim().replace(/[^\w-]+/g, '_').replace(/^_+|_+$/g, '') || 'Assignment';
    },

    getExportDateSuffix() {
      return this.submissionDate || todayIso;
    },

    pruneHiddenForExport(root) {
      root.querySelectorAll('[style*="display: none"], [style*="display:none"]').forEach((el) => {
        el.remove();
      });
    },

    createExportStage() {
      const source = document.getElementById('cover-page');
      if (!source) throw new Error('Cover page not found.');

      const stage = document.createElement('div');
      stage.className = 'export-stage';

      const clone = source.cloneNode(true);
      clone.id = 'cover-page-export';
      clone.style.width = `${A4_WIDTH_PX}px`;
      clone.style.minHeight = `${A4_HEIGHT_PX}px`;
      clone.style.height = `${A4_HEIGHT_PX}px`;
      clone.style.transform = 'none';
      clone.style.scale = '1';
      this.pruneHiddenForExport(clone);

      stage.appendChild(clone);
      document.body.appendChild(stage);
      return { stage, clone };
    },

    async waitForExportAssets(container) {
      if (document.fonts?.ready) {
        try { await document.fonts.ready; } catch (_) { /* ignore */ }
      }
      const images = Array.from(container.querySelectorAll('img'));
      await Promise.all(images.map((img) => {
        if (img.complete) return Promise.resolve();
        return new Promise((resolve) => {
          img.addEventListener('load', resolve, { once: true });
          img.addEventListener('error', resolve, { once: true });
        });
      }));
    },

    async renderCoverCanvas() {
      const { stage, clone } = this.createExportStage();
      try {
        await this.waitForExportAssets(clone);
        if (typeof html2canvas === 'undefined') {
          throw new Error('Export library not loaded. Please refresh the page.');
        }
        return await html2canvas(clone, {
          scale: EXPORT_SCALE,
          backgroundColor: '#ffffff',
          allowTaint: true,
          useCORS: true,
          logging: false,
          imageTimeout: 8000,
          width: A4_WIDTH_PX,
          height: A4_HEIGHT_PX,
          windowWidth: A4_WIDTH_PX,
          windowHeight: A4_HEIGHT_PX,
        });
      } finally {
        stage.remove();
      }
    },

    async downloadPdf() {
      if (!this.validateForm()) return;
      if (!window.jspdf?.jsPDF) {
        alert('PDF library not loaded. Please refresh the page.');
        return;
      }
      this.exportBusy = true;
      this.saveDraft();
      try {
        const canvas = await this.renderCoverCanvas();
        const imageData = canvas.toDataURL('image/png');
        const pdf = new window.jspdf.jsPDF({
          orientation: 'portrait',
          unit: 'mm',
          format: 'a4',
          compress: true,
        });
        pdf.addImage(imageData, 'PNG', 0, 0, A4_WIDTH_MM, A4_HEIGHT_MM, undefined, 'FAST');
        pdf.save(`Assignment_${this.getSafeFilename()}_${this.getExportDateSuffix()}.pdf`);
      } catch (err) {
        alert(`PDF export failed: ${err.message || err}`);
      } finally {
        this.exportBusy = false;
      }
    },

    async downloadPng() {
      if (!this.validateForm()) return;
      this.exportBusy = true;
      this.saveDraft();
      try {
        const canvas = await this.renderCoverCanvas();
        const blob = await new Promise((resolve, reject) => {
          canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Failed to create PNG.'))), 'image/png');
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `Assignment_${this.getSafeFilename()}_${this.getExportDateSuffix()}.png`;
        link.click();
        URL.revokeObjectURL(url);
      } catch (err) {
        alert(`PNG export failed: ${err.message || err}`);
      } finally {
        this.exportBusy = false;
      }
    },

    printPdf() {
      this.saveDraft();
      window.print();
    },
  };
}

if (typeof window !== 'undefined') {
  window.coverPageGenerator = coverPageGenerator;
  const registerAlpineCover = () => {
    if (window.Alpine?.data) window.Alpine.data('coverPageGenerator', coverPageGenerator);
  };
  if (window.Alpine) registerAlpineCover();
  else document.addEventListener('alpine:init', registerAlpineCover);
}
