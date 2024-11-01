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

            # Load the original image for this iteration
            image = Image.open(image_name)
            draw = ImageDraw.Draw(image)

            if number_option == "continuous":
                i = n
                with open(csv_name) as csvfile:
                    for x, y in csv.reader(csvfile, delimiter=','):
                        coordx = int(x)
                        coordy = int(y)
                        string = f'{i}'

                        if skip_option == "skip":
                            with open(special_case_name) as csvspecial:
                                for row in csv.reader(csvspecial, delimiter=','):
                                    if string == f'{row[0]}':
                                        i += 1
                                        string = f'{i}'

                        if draw_shape == "circle":
                            draw.ellipse([(coordx - 11, coordy - 11), (coordx + 11, coordy + 11)], fill='white',
                                         outline='black')
                        elif draw_shape == "square":
                            draw.rectangle([(coordx - 9, coordy - 9), (coordx + 9, coordy + 9)], fill='white',
                                           outline='black')

                        draw.text((coordx + 1, coordy), string, fill='red', anchor='mm', font=font)
                        i += 1
                        if i > m:
                            break

            elif number_option == "special":
                i = n
                with open(csv_name) as csvfile:
                    for x, y in csv.reader(csvfile, delimiter=','):
                        coordx = int(x)
                        coordy = int(y)
                        string = ""

                        with open(special_case_name) as csvspecial:
                            for k, row in enumerate(csv.reader(csvspecial, delimiter=','), start=1):
                                if k == i:
                                    string = f'{row[0]}'
                                    break

                        if draw_shape == "circle":
                            draw.ellipse([(coordx - 11, coordy - 11), (coordx + 11, coordy + 11)], fill='white',
                                         outline='black')
                        elif draw_shape == "square":
                            draw.rectangle([(coordx - 11, coordy - 11), (coordx + 11, coordy + 11)], fill='white',
                                           outline='black')

                        draw.text((coordx + 1, coordy), string, fill='black', anchor='mm', font=font)
                        i += 1
                        if i > m:
                            break

            # Save each modified image under its unique name
            image.save(export_name)

        return 'ok'

    except Exception as e:
        print(f"Error in generate_plan: {e}")
        return str(e)
