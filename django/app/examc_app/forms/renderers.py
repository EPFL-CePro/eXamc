from django.forms.renderers import TemplatesSetting


class DefaultFormRenderer(TemplatesSetting):
    field_template_name = "forms/field.html"