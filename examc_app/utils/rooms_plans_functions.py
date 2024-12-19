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

            # Charger l'image d'origine
            image = Image.open(image_name)
            draw = ImageDraw.Draw(image)

            # Lire les numéros spéciaux à ignorer
            skipped_numbers = set()
            if skip_option == "skip":
                with open(special_case_name) as csvspecial:
                    skipped_numbers = {row[0] for row in csv.reader(csvspecial, delimiter=',')}

            i = n  # Numéro actuel
            with open(csv_name) as csvfile:
                for x, y in csv.reader(csvfile, delimiter=','):
                    coordx = int(x)
                    coordy = int(y)

                    # Passer les numéros à ignorer
                    while str(i) in skipped_numbers:
                        i += 1

                    string = f'{i}'

                    # Dessiner la forme (cercle ou carré)
                    if draw_shape == "circle":
                        draw.ellipse([(coordx - 11, coordy - 11), (coordx + 11, coordy + 11)], fill='white',
                                     outline='black')
                    elif draw_shape == "square":
                        draw.rectangle([(coordx - 9, coordy - 9), (coordx + 9, coordy + 9)], fill='white',
                                       outline='black')

                    # Ajouter le numéro
                    draw.text((coordx + 1, coordy), string, fill='red', anchor='mm', font=font)
                    i += 1  # Incrémenter pour le prochain siège

            # Sauvegarder l'image modifiée
            image.save(export_name)

        return 'ok'

    except Exception as e:
        print(f"Error in generate_plan: {e}")
        return str(e)

