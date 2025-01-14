from PIL import Image, ImageDraw, ImageFont
import csv
from django.conf import settings


def generate_plan(csv_data, image_file, csv_file, export_file, numbering_option, skipping_option, first_seat, last_seat,
                  special_file, shape):
    try:
        font = ImageFont.truetype(str(settings.ROOMS_PLANS_ROOT) + "/NotoSans-Bold.ttf", 10)

        for map, coord_file, export, number_option, skip_option, start, end, special_case, draw_option in csv_data:

            image_name = str(settings.ROOMS_PLANS_ROOT) + "/map/" + map
            csv_name = str(settings.ROOMS_PLANS_ROOT) + "/csv/" + coord_file
            n = int(start)
            m = int(end)
            export_name = str(settings.ROOMS_PLANS_ROOT) + "/export/" + export
            draw_shape = draw_option
            special_case_name = str(settings.ROOMS_PLANS_ROOT) + "/csv_special_numbers/" + special_case

            image = Image.open(image_name)
            draw = ImageDraw.Draw(image)

            skip_numbers = []
            if skip_option == "skip" and special_case:
                with open(special_case_name) as csvspecial:
                    skip_numbers = [int(row[0]) for row in csv.reader(csvspecial, delimiter=',')]

            special_numbers = []
            if number_option == "special":
                with open(special_case_name) as csvspecial:
                    special_numbers = [row[0] for row in csv.reader(csvspecial, delimiter=',')]

            current_number = n
            with open(csv_name) as csvfile:
                for i, (x, y) in enumerate(csv.reader(csvfile, delimiter=','), start=1):
                    coordx = int(x)
                    coordy = int(y)

                    if number_option == "special":
                        if i <= len(special_numbers):
                            text = special_numbers[i - 1]
                        else:
                            text = ""
                    else:

                        while skip_option == "skip" and current_number in skip_numbers:
                            current_number += 1
                        text = str(current_number)

                    if draw_shape == "circle":
                        draw.ellipse([(coordx - 11, coordy - 11), (coordx + 11, coordy + 11)], fill='white',
                                     outline='black')
                    elif draw_shape == "square":
                        draw.rectangle([(coordx - 9, coordy - 9), (coordx + 9, coordy + 9)], fill='white',
                                       outline='black')

                    draw.text((coordx + 1, coordy), text, fill='red', anchor='mm', font=font)

                    if number_option != "special":
                        current_number += 1

                    if current_number > m:
                        break

            image.save(export_name)

        return 'ok'

    except Exception as e:
        print(f"Error in generate_plan: {e}")
        return str(e)
