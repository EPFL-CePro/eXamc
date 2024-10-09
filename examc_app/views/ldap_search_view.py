import row

from examc_app.utils.epflldap import ldap_search
from ..forms import ldapForm
from ..utils.epflldap.ldap_search import LDAP_search
from django.shortcuts import render
from django.contrib import messages
import pandas as pd
from django.http import HttpResponse
import csv


def get_entry(searchvalue,searchattribute):
    """
    return user ldap entry
    """
    response = LDAP_search(
        pattern_search='('+searchattribute+'={})'.format(searchvalue),
    )
    try:
        if len(response) > 0:
            list = []
            for entry in response:
                ldap_entry = response[entry]['attributes']
                list.append(ldap_entry)
                # print(list)
                return list
        else:
            return None
    except Exception as e:
        print(e)
        return e

def upload_excel_generate_csv(request):
    if request.method == 'POST':
        form = ldapForm(request.POST)

        if form.is_valid() and 'file' in request.FILES:
            file = request.FILES['file']
            search_choice = form.cleaned_data['choice']

            df = pd.read_excel(file)
            data = []


            for index, row in df.iterrows():

                ldap_entries = ldap_search.get_entry(row[0], search_choice)
                print(ldap_entries)
                if ldap_entries:

                    sciper = ldap_entries.get('uniqueidentifier', [''])[0]
                    first_name = ldap_entries.get('givenName', [''])[0]
                    last_name = ldap_entries.get('sn', [''])[0]
                    email = ldap_entries.get('mail', [''])[0]
                    ou = ldap_entries.get('ou', [''])[0]
                    employee_type = ldap_entries.get('employeeType', [''])[0]
                    title = ldap_entries.get('title', [''])[0]
                    uid = ldap_entries.get('uid', [''])[0]

                    row_data = {
                        'Sciper': sciper,
                        'First name': first_name,
                        'Last name': last_name,
                        'Email': email,
                        'OU': ou,
                        'Employee type': employee_type,
                        'Title': title,
                        'uid': uid
                    }
                    data.append(row_data)
                else:
                    messages.warning(request, f'No LDAP entry found for {row[0]} in the LDAP.')

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="data.csv"'

            writer = csv.DictWriter(response,
                                    fieldnames=['Sciper', 'First name', 'Last name', 'Email', 'OU', 'Employee type', 'Title', 'uid'])
            writer.writeheader()
            writer.writerows(data)

            return response

    else:
        form = ldapForm()

    return render(request, 'search_ldap/search.html', {'form': form})