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

            # Charger l'image originale pour cette itération
            image = Image.open(image_name)
            draw = ImageDraw.Draw(image)

            # Charger les numéros à skipper si skipping_option == "skip"
            skip_numbers = []
            if skip_option == "skip" and special_case:
                with open(special_case_name) as csvspecial:
                    skip_numbers = [int(row[0]) for row in csv.reader(csvspecial, delimiter=',')]

            # Gérer le "continuous" numbering
            current_number = n  # Commence à partir du premier numéro
            with open(csv_name) as csvfile:
                for x, y in csv.reader(csvfile, delimiter=','):
                    coordx = int(x)
                    coordy = int(y)

                    # Déterminer si le numéro doit être skippé
                    while skip_option == "skip" and current_number in skip_numbers:
                        current_number += 1  # Sauter ce numéro

                    # Dessiner la forme (place toujours dessinée)
                    if draw_shape == "circle":
                        draw.ellipse([(coordx - 11, coordy - 11), (coordx + 11, coordy + 11)], fill='white',
                                     outline='black')
                    elif draw_shape == "square":
                        draw.rectangle([(coordx - 9, coordy - 9), (coordx + 9, coordy + 9)], fill='white',
                                       outline='black')

                    # Dessiner le numéro uniquement si on ne l'a pas skippé
                    draw.text((coordx + 1, coordy), str(current_number), fill='red', anchor='mm', font=font)

                    current_number += 1  # Passer au numéro suivant
                    if current_number > m:
                        break

            # Sauvegarder l'image modifiée
            image.save(export_name)

        return 'ok'

    except Exception as e:
        print(f"Error in generate_plan: {e}")
        return str(e)


