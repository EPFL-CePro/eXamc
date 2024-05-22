from django.contrib.auth.decorators import login_required
import shutil
import zipfile

from django.utils.decorators import method_decorator

from examc_app.utils.review_functions import *
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.http import FileResponse, HttpResponse
from examc import settings

from examc_app.forms import SeatingForm
from examc_app.utils.rooms_plans_functions import generate_plan


@method_decorator(login_required(login_url='/'), name='dispatch')
class GenerateRoomPlanView(FormView):
    template_name = 'rooms_plans/rooms_plans.html'
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
        csv_files = form.cleaned_data['csv_file']
        image_files = [csv_file.replace('.csv', '.jpg') for csv_file in csv_files]
        numbering_option = form.cleaned_data['numbering_option']
        skipping_option = form.cleaned_data['skipping_option']
        first_seat_number = form.cleaned_data['first_seat_number']
        last_seat_number = form.cleaned_data['last_seat_number']
        special_file = form.cleaned_data['special_file']
        shape_to_draw = form.cleaned_data['shape_to_draw']

        # Write parameters to CSV for each file
        with open(str(settings.ROOMS_PLANS_ROOT)+"/param.csv", mode='w', newline='') as file:
            writer = csv.writer(file)
            for i in range(len(csv_files)):
                image_file = image_files[i]
                csv_file = csv_files[i]
                export_file = image_file.replace('.jpg', '_export.jpg')
                writer.writerow([image_file, csv_file, export_file, numbering_option, skipping_option,
                                 first_seat_number, last_seat_number, special_file, shape_to_draw])

        # Execute the script for each CSV file
        responses = []
        export_files = []
        for i in range(len(csv_files)):
            image_file = image_files[i]
            csv_file = csv_files[i]
            image_file = image_files[i]
            export_file = image_file.replace('.jpg', '_export.jpg')
            #script_path = "examc_app/scripts/rooms_plans_functions.py"
            result = generate_plan(image_file,
                csv_file,
                export_file,
                numbering_option,
                skipping_option,
                str(first_seat_number),
                str(last_seat_number),
                special_file,
                shape_to_draw)

            if result == 'ok':
            # command = [
            #     "python3", script_path,
            #     image_file,
            #     csv_file,
            #     export_file,
            #     numbering_option,
            #     skipping_option,
            #     str(first_seat_number),
            #     str(last_seat_number),
            #     special_file,
            #     shape_to_draw
            # ]
            #
            # process = Popen(command, stdout=PIPE, stderr=PIPE)
            # stdout, stderr = process.communicate()
                export_file_path = str(settings.ROOMS_PLANS_ROOT)+"/export/"+export_file
                if os.path.exists(export_file_path):
                    export_files.append(export_file_path)
                else:
                    logger.error(f"No export file found for {export_file}.")
                    return HttpResponse(f"No export file found for {export_file}.", status=404)
            else:
                return HttpResponse("Error during plan generation : "+result)

            # Create a ZIP file containing all the export files
        zip_filename = 'exported_seating_maps.zip'
        zip_filepath = str(settings.ROOMS_PLANS_ROOT)+"/export/"+zip_filename
        with zipfile.ZipFile(zip_filepath, 'w') as zipf:
            for export_file in export_files:
                zipf.write(export_file, os.path.basename(export_file))

        # Remove individual export files after adding them to the ZIP
        for export_file in export_files:
            os.remove(export_file)

        # Return the ZIP file as a response
        if os.path.exists(zip_filepath):
            f = open(zip_filepath, 'rb')
            response = FileResponse(f)
            response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
            return response
        else:
            return HttpResponse("No ZIP file found.", status=404)