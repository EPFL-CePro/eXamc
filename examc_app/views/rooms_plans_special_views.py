from django.views.generic.edit import FormView
from examc_app.forms import SeatingSpecialForm


class GenerateRoomPlanSpecialView(FormView):
    template_name = 'rooms_plans/rooms_plans_special.html'
    form_class = SeatingSpecialForm
