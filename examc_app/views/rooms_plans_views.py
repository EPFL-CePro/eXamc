import csv

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

CSV_TO_JPG_MAP = {
    'AAC_120.csv': 'AAC_120.jpg',
    'AAC_132.csv': 'AAC_132.jpg',
    'AAC_137.csv': 'AAC_137.jpg',
    'AAC_231.csv': 'AAC_231.jpg',
    'BCH_2201.csv': 'BCH_2201.jpg',
    'BS_150.csv': 'BS_150.jpg',
    'BS_150_soft.csv': 'BS_150.jpg',
    'BS_160.csv': 'BS_160.jpg',
    'BS_170.csv': 'BS_170.jpg',
    'BS_260.csv': 'BS_260.jpg',
    'BS_270.csv': 'BS_270.jpg',
    'CE_1_1.csv': 'CE_1_1.jpg',
    'CE_1_2.csv': 'CE_1_2.jpg',
    'CE_1_3.csv': 'CE_1_3.jpg',
    'CE_1_4.csv': 'CE_1_4.jpg',
    'CE_1_5.csv': 'CE_1_5.jpg',
    'CE_1_6.csv': 'CE_1_6.jpg',
    'CE_1_soft.csv': 'CE_1_1.jpg',
    'CE_3_soft.csv': 'CE_1_1.jpg',
    'CE_1100.csv': 'CE_1100.jpg',
    'CE_1104.csv': 'CE_1104.jpg',
    'CE_1105.csv': 'CE_1105.jpg',
    'CE_1106.csv': 'CE_1106.jpg',
    'CE_1515_bas.csv': 'CE_1515_bas.jpg',
    'CE_1515_haut.csv': 'CE_1515_haut.jpg',
    'CH_B3_30.csv': 'CH_B3_30.jpg',
    'CM_1_1.csv': 'CM_1_1.jpg',
    'CM_1_2.csv': 'CM_1_2.jpg',
    'CM_1_3.csv': 'CM_1_3.jpg',
    'CM_1_4.csv': 'CM_1_4.jpg',
    'CM_1_5.csv': 'CM_1_5.jpg',
    'CM_1106.csv': 'CM_1106.jpg',
    'CM_1120.csv': 'CM_1120.jpg',
    'CM_1121.csv': 'CM_1121.jpg',
    'CO_01.csv': 'CO_01.jpg',
    'CO_02.csv': 'CO_02.jpg',
    'CO_03.csv': 'CO_03.jpg',
    'INJ_218.csv': 'INJ_218.jpg',
    'MA_A1_10.csv': 'MA_A1_10.jpg',
    'MA_A1_12.csv': 'MA_A1_12.jpg',
    'PO_01_exam.csv': 'PO_01_exam.jpg',
    'PO_01_old.csv': 'PO_01_old.jpg',
    'PO_01_old_exam.csv': 'PO_01_old.jpg',
    'SG_0211.csv': 'SG_0211.jpg',
    'SG_0213.csv': 'SG_0213.jpg',
    'SG_1138.csv': 'SG_1138.jpg',
    'STCC_A.csv': 'STCC.jpg',
    'STCC_B.csv': 'STCC.jpg',
    'STCC_C.csv': 'STCC.jpg',
    'STCC_D.csv': 'STCC.jpg',
    'STCC_E.csv': 'STCC.jpg',
    'STCC_F.csv': 'STCC.jpg',
    'STCC_G.csv': 'STCC.jpg',
    'STCC_H.csv': 'STCC.jpg',
}


def count_csv_lines(file_path):
    try:
        with open(file_path, 'r', newline='') as file:
            reader = csv.reader(file)
            line_count = sum(1 for row in reader if any(row))
        return line_count
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return None


@method_decorator(login_required(login_url='/'), name='dispatch')
class GenerateRoomPlanView(FormView):
    template_name = 'rooms_plans/rooms_plans.html'
    form_class = SeatingForm
    success_url = reverse_lazy('success')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form2'] = SeatingForm()
        return context

    def post(self, request, *args, **kwargs):
        form = SeatingForm(request.POST, prefix='form')
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):

        csv_files = form.cleaned_data['csv_file']
        image_files = [CSV_TO_JPG_MAP[csv_file] for csv_file in csv_files]
        numbering_option = form.cleaned_data['numbering_option']
        skipping_option = form.cleaned_data['skipping_option']
        first_seat_number = form.cleaned_data['first_seat_number']
        # last_seat_number = form.cleaned_data['last_seat_number']
        special_file = form.cleaned_data['special_file']
        shape_to_draw = form.cleaned_data['shape_to_draw']
        fill_all_seats = form.cleaned_data['fill_all_seats']

        total_seats = 0
        current_seat_number = first_seat_number
        # Write parameters to CSV for each file
        with open(str(settings.ROOMS_PLANS_ROOT) + "/param.csv", mode='w', newline='') as file:
            writer = csv.writer(file)
            for i in range(len(csv_files)):
                image_file = image_files[i]
                csv_file = csv_files[i]
                export_file = image_file.replace('.jpg', '_export.jpg')

                # Calculate total seats in the current CSV file
                total_seats = count_csv_lines(str(settings.ROOMS_PLANS_ROOT) + '/csv/' + csv_file)
                if total_seats is None:
                    return HttpResponse(f"Error reading CSV file: {csv_file}", status=500)

                if fill_all_seats:
                    # Fill all seats based on the CSV content
                    first_seat_number = current_seat_number
                    last_seat_number = current_seat_number + total_seats - 1
                else:
                    # Use provided first and last seat numbers
                    if i == 0:
                        # For the first file, use provided first and last seat numbers
                        first_seat_number = form.cleaned_data['first_seat_number']
                        last_seat_number = form.cleaned_data['last_seat_number']
                    else:
                        first_seat_number = form.cleaned_data['first_seat_number'] + total_seats - 1
                        if current_seat_number + total_seats - 1 > last_seat_number:
                            total_seats = last_seat_number - current_seat_number + 1
                        last_seat_number = current_seat_number + total_seats - 1

                writer.writerow([image_file, csv_file, export_file, numbering_option, skipping_option,
                                 first_seat_number, last_seat_number, special_file, shape_to_draw])

                # Update current_seat_number for the next file
                current_seat_number = last_seat_number + 1

        responses = []
        export_files = []
        for i in range(len(csv_files)):
            image_file = image_files[i]
            csv_file = csv_files[i]
            export_file = image_file.replace('.jpg', '_export.jpg')

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

                export_file_path = str(settings.ROOMS_PLANS_ROOT) + "/export/" + export_file
                if os.path.exists(export_file_path):
                    export_files.append(export_file_path)
                else:
                    logger.error(f"No export file found for {export_file}.")
                    return HttpResponse(f"No export file found for {export_file}.", status=404)
            else:
                return HttpResponse("Error during plan generation : " + result)

            # Create a ZIP file containing all the export files
        zip_filename = 'exported_seating_maps.zip'
        zip_filepath = str(settings.ROOMS_PLANS_ROOT) + "/export/" + zip_filename
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
