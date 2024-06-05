import csv
import math
import os
import shutil
import zipfile
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.http import FileResponse, HttpResponse
from self import self

from examc_app.utils.review_functions import *
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
    'BS_150_soft.csv': 'BS_150_soft.jpg',
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
    'STCC_B.csv': 'STCC_B.jpg',
    'STCC_C.csv': 'STCC_C.jpg',
    'STCC_D.csv': 'STCC_D.jpg',
    'STCC_E.csv': 'STCC_E.jpg',
    'STCC_F.csv': 'STCC_F.jpg',
    'STCC_G.csv': 'STCC_G.jpg',
    'STCC_H.csv': 'STCC_H.jpg',
}


def count_csv_lines(file_path):
    """
       Counts the number of non-empty lines in a CSV file.

       Args:
           file_path (str): Path to the CSV file.

       Returns:
           int: Number of non-empty lines in the CSV file.
       """
    try:
        with open(file_path, 'r', newline='') as file:
            reader = csv.reader(file)
            line_count = sum(1 for row in reader if any(row))
        return line_count
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return None


def calculate_seat_numbers(csv_files, first_seat_number, last_seat_number, count_csv_lines):
    """
        Calculates the first and last seat numbers for each CSV file.

        Args:
            csv_files (list): List of paths to CSV files.
            first_seat_number (int): The first seat number.
            last_seat_number (int): The last seat number.
            count_csv_lines (function): Function to count lines in a CSV file.

        Returns: tuple: Two lists representing the first and last seat numbers for each file.
        """
    try:
        N = [0] * len(csv_files)
        F = [0] * len(csv_files)
        L = [0] * len(csv_files)

        F[0] = first_seat_number
        maxN = last_seat_number

        total_seats = sum(count_csv_lines(file) for file in csv_files)

        ratio = (last_seat_number - first_seat_number + 1) / total_seats
        ratio = min(ratio, 1)

        for j in range(len(csv_files)):
            N[j] = count_csv_lines(csv_files[j])

            L[j] = math.ceil(N[j] * ratio) + F[j] - 1
            if j < len(csv_files) - 1:
                F[j + 1] = L[j] + 1
            else:
                L[j] = min(L[j], maxN)

            if L[j] < F[j]:
                raise ValueError("Negative number of seats selected")

        return F, L
    except Exception as e:
        print(f"Error calculating seat numbers: {e}")
        return None, None


# @method_decorator(login_required(login_url='/'), name='dispatch')
class GenerateRoomPlanView(FormView):
    template_name = 'rooms_plans/rooms_plans.html'
    form_class = SeatingForm
    success_url = reverse_lazy('success')

    def form_valid(self, form):

        csv_files = form.cleaned_data['csv_file']
        image_files = [CSV_TO_JPG_MAP[csv_file] for csv_file in csv_files]
        numbering_option = form.cleaned_data['numbering_option']
        skipping_option = form.cleaned_data['skipping_option']
        first_seat_number = form.cleaned_data['first_seat_number']
        last_seat_number = form.cleaned_data['last_seat_number']
        special_file = form.cleaned_data['special_file']
        shape_to_draw = form.cleaned_data['shape_to_draw']
        fill_all_seats = form.cleaned_data['fill_all_seats']

        total_seats = []
        special_files_paths = []
        current_seat_number = first_seat_number

        if special_file:
            fs = FileSystemStorage(location=str(settings.ROOMS_PLANS_ROOT) + '/csv_special_numbers')
            filename = fs.save(special_file.name, special_file)
            special_file_path = fs.path(filename)
            special_files_paths.append(special_file_path)
        else:
            special_file_path = None
        csv_file_paths = [str(settings.ROOMS_PLANS_ROOT) + '/csv/' + csv_file for csv_file in csv_files]
        F, L = calculate_seat_numbers(csv_file_paths, first_seat_number, last_seat_number or sum([count_csv_lines(f)
                                                                                                  for f in
                                                                                                  csv_file_paths]),
                                      count_csv_lines)

        with open(str(settings.ROOMS_PLANS_ROOT) + "/param.csv", mode='w', newline='') as file:
            writer = csv.writer(file)
            for i in range(len(csv_files)):
                image_file = image_files[i]
                csv_file = csv_files[i]
                export_file = image_file.replace('.jpg', '_export.jpg')
                total_seats = count_csv_lines(str(settings.ROOMS_PLANS_ROOT) + '/csv/' + csv_file)
                if total_seats is None:
                    return HttpResponse(f"Error reading CSV file: {csv_file}", status=500)

                if skipping_option == 'skip':
                    if fill_all_seats:
                        if i == 0:
                            first_seat_number = form.cleaned_data['first_seat_number']
                            last_seat_number = first_seat_number + total_seats - 1
                        else:
                            first_seat_number = last_seat_number + 1
                            last_seat_number = last_seat_number + total_seats - 1
                    else:
                        first_seat_number = F[i]
                        last_seat_number = L[i]

                elif numbering_option == 'special':
                    first_seat_number = 1
                    if fill_all_seats:
                        last_seat_number = first_seat_number + total_seats - 1
                    else:
                        last_seat_number = form.cleaned_data['last_seat_number']

                else:
                    if fill_all_seats:
                        first_seat_number = current_seat_number
                        last_seat_number = current_seat_number + total_seats - 1
                    else:
                        first_seat_number = F[i]
                        last_seat_number = L[i]

                current_seat_number = last_seat_number + 1
                writer.writerow([image_file, csv_file, export_file, numbering_option, skipping_option,
                                 first_seat_number, last_seat_number, special_file, shape_to_draw])
        responses = []
        export_files = []
        export_files_url = []
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
                export_file_path = os.path.join(settings.ROOMS_PLANS_ROOT, "export", export_file)
                if os.path.exists(export_file_path):
                    export_files.append(export_file_path)
                    export_file_url = os.path.join(settings.ROOMS_PLANS_URL, "export", export_file)
                    export_files_url.append(export_file_url)
                else:
                    logger.error(f"No export file found for {export_file}.")
                    return HttpResponse(f"No export file found for {export_file}.", status=404)
            else:
                return HttpResponse("Error during plan generation : " + result)

        zip_filename = 'exported_seating_maps.zip'
        zip_filepath = os.path.join(settings.ROOMS_PLANS_ROOT, "export", zip_filename)

        with zipfile.ZipFile(zip_filepath, 'w') as zipf:
            for export_file in export_files:
                zipf.write(export_file, os.path.basename(export_file))

        if self.request.POST.get('action') == 'preview':
            if export_files:
                return render(self.request, 'rooms_plans/rooms_plans.html', {'export_files': export_files_url})
            else:
                return HttpResponse("No export files found.", status=404)

        elif self.request.POST.get('action') == 'download':
            zip_filename = 'exported_seating_maps.zip'
            zip_filepath = os.path.join(settings.ROOMS_PLANS_ROOT, "export", zip_filename)

            for export_file in export_files:
                os.remove(export_file)

            for special_file_path in special_files_paths:
                os.remove(special_file_path)

            if os.path.exists(zip_filepath):
                f = open(zip_filepath, 'rb')
                response = FileResponse(f)
                response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
                return response

            else:
                return HttpResponse("No ZIP file found.", status=404)
