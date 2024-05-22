from django.contrib.auth.decorators import login_required

from examc_app.utils.review_functions import *
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.http import FileResponse, HttpResponse
from subprocess import Popen, PIPE

from examc_app.forms import SeatingForm

def remove_bad_substrings(s):
    badSubstrings = [".csv"]
    for badSubstring in badSubstrings:
        s = s.replace(badSubstring, ".jpg")
    return s
@method_decorator(login_required(login_url='/'), name='dispatch')
class GenerateSeatingView(FormView):
    template_name = 'room/seating_script.html'
    form_class = SeatingForm
    success_url = reverse_lazy('success')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form2'] = SeatingForm()  # Add the second form instance to the context
        return context

    def post(self, request, *args, **kwargs):
        form = SeatingForm(request.POST, prefix='form')


        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        image_file = form.cleaned_data['csv_file']
        image_file = [image_file.replace('.csv', '.jpg') for image_file in image_file]
        image_file = "".join(image_file)
        csv_files = form.cleaned_data['csv_file']
        export_file = image_file
        numbering_option = form.cleaned_data['numbering_option']
        skipping_option = form.cleaned_data['skipping_option']
        first_seat_number = form.cleaned_data['first_seat_number']
        last_seat_number = form.cleaned_data['last_seat_number']
        special_file = form.cleaned_data['special_file']
        shape_to_draw = form.cleaned_data['shape_to_draw']

        script_path = "examc_app/scripts/generate_seating.py"
        command = [
            "python3", script_path,
            image_file,
            ",".join(csv_files),
            export_file,
            numbering_option,
            skipping_option,
            str(first_seat_number),
            str(last_seat_number),
            special_file,
            shape_to_draw
        ]
        with open('examc_app/scripts/param.csv', mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([image_file, ",".join(csv_files), export_file, numbering_option, skipping_option,
                             first_seat_number, last_seat_number, special_file, shape_to_draw])

        process = Popen(command, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()

        export_file_path = os.path.join("examc_app/scripts/export", export_file)

        if os.path.exists(export_file_path):
            f = open(export_file_path, "rb")
            #with open(export_file_path, 'rb') as f:
            response = FileResponse(f)
            response['Content-Disposition'] = f'attachment; filename="{export_file}"'
            return response
        else:
            return HttpResponse("No export file found.", status=404)
