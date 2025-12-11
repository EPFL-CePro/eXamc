from PIL import Image, ImageDraw, ImageFont
import csv
from django.conf import settings


def generate_plan(csv_data, image_file, csv_file, export_file, first_seat, last_seat,
                  shape):
    try:
        font = ImageFont.truetype(str(settings.ROOMS_PLANS_ROOT) + "/NotoSans-Bold.ttf", 10)

        for map, coord_file, export, start, end, draw_option in csv_data:

            image_name = str(settings.ROOMS_PLANS_ROOT) + "/map/" + map
            csv_name = str(settings.ROOMS_PLANS_ROOT) + "/csv/" + coord_file
            n = int(start)
            m = int(end)
            export_name = str(settings.ROOMS_PLANS_ROOT) + "/export/" + export
            draw_shape = draw_option

            image = Image.open(image_name)
            draw = ImageDraw.Draw(image)

            # if number_option == "skip_places":
            #     skip_numbers = skip_places

            current_number = n
            with open(csv_name) as csvfile:
                for i, (x, y) in enumerate(csv.reader(csvfile, delimiter=','), start=1):
                    coordx = int(x)
                    coordy = int(y)

                    if draw_shape == "circle":
                        draw.ellipse([(coordx - 11, coordy - 11), (coordx + 11, coordy + 11)], fill='white',
                                     outline='black')
                    elif draw_shape == "square":
                        draw.rectangle([(coordx - 9, coordy - 9), (coordx + 9, coordy + 9)], fill='white',
                                       outline='black')
                        
                    text = str(current_number)

                    draw.text((coordx + 1, coordy), text, fill='red', anchor='mm', font=font)

                    current_number += 1

                    if current_number > m:
                        break

            image.save(export_name)

        return 'ok'

    except Exception as e:
        print(f"Error in generate_plan: {e}")
        return str(e)
