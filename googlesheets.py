import os

import httplib2
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials

import creds


# def get_service_simple():
#     return build('sheets', 'v4', developerKey=creds.api_key)


def get_service_sacc():
    """
    Могу читать и (возможно) писать в таблицы кот. выдан доступ
    для сервисного аккаунта приложения
    sacc-1@privet-yotube-azzrael-code.iam.gserviceaccount.com
    :return:
    """
    creds_json = os.path.dirname(__file__) + "/secrets/botchelenge-a3d82165b345.json"
    scopes = ['https://www.googleapis.com/auth/spreadsheets']

    creds_service = ServiceAccountCredentials.from_json_keyfile_name(creds_json, scopes).authorize(httplib2.Http())
    return build('sheets', 'v4', http=creds_service)


# service = get_service_simple()
service = get_service_sacc()
sheet = service.spreadsheets()

# https://docs.google.com/spreadsheets/d/xxx/edit#gid=0
sheet_id = "1O8ey-FM3QwiYhCwj5DS7ERWsRmaQ8ze06Tu4J2CfwQM"

# https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values/get
resp = sheet.values().get(spreadsheetId=sheet_id, range="Лист1!A1:A999").execute()

# https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values/batchGet
# resp = sheet.values().batchGet(spreadsheetId=sheet_id, ranges=["Лист1", "Лист2"]).execute()

print(resp['values'])

body = {
    'values' : [
        ["Шебалкин Антон Сергеевич", "04/12/2022", 1234456, 'link'], # строка
    ]
}

resp = sheet.values().append(
    spreadsheetId=sheet_id,
    range="Лист1!A2:L99",
    valueInputOption="RAW",
    body=body).execute()