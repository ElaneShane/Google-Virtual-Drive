# SETUP: install these libraries
# create service account credentials from Google Cloud and save the json keyfile in `credentials.json`
# tutorial: https://spreadsheetpoint.com/connect-python-and-google-sheets-15-minute-guide/
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from torchmetrics.text import CharErrorRate

# SHOULD NOT LOAD EXCEL FOR EACH BOUNDING BOX!!!
# maybe load once every iteration of drive

def load_excel():
    # Define the scope of API
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    # Authenticate with credentials
    credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(credentials)

    # Open the Google Sheet
    MASTER_SHEET_INDEX = 0
    sheet = client.open('Tracker - Merged Master Sign Catalog ').get_worksheet(MASTER_SHEET_INDEX)
    return sheet.get_all_records() # return all unique signs in the Google sheet

# have a list of ocr candidate
def specifySigns(baseSign, words, ocr_candidate_signs):
    cer = CharErrorRate()
    cers = {}
    prediction = " ".join(words)
    lowest_cer = ""
    # for each sign type
    for ocr_candidate_sign in ocr_candidate_signs:
        if (ocr_candidate_sign["Bounding box name"] == baseSign):
            ocr_desc = " ".join(ocr_candidate_sign["OCR Desc"].split('\n'))
            # calculate CER
            cer_val = cer(prediction, ocr_desc).item() / len(ocr_desc)
            print(f'CER Value: {cer_val}\tOCR desc: {ocr_desc};\tMUTCD Code:{ocr_candidate_sign["MUTCD_CODE"]};\tUnique Stock Num: {ocr_candidate_sign["UNIQUE STOCK_NUMBER"]}-{ocr_candidate_sign["UNIQUE STOCK_NUMBER_1"]}-{ocr_candidate_sign["UNIQUE STOCK_NUMBER_2"]};\tDescription:{ocr_candidate_sign["DESCRIPTION"]}')
            # is the `lowest_cer != ""` check necesssary?
            if (len(cers) == 0 or (lowest_cer != "" and cer_val < cers[lowest_cer])):
                lowest_cer = ocr_desc
            cers[ocr_desc] = cer_val

    return lowest_cer, cers

def is_ocr_canditate(unique_sign):
    return unique_sign["OCR candidate?"] == "y"

def test(baseSign, words):
    unique_signs: list[dict] = load_excel()
    lowest_cer, cers = specifySigns(baseSign, words, filter(is_ocr_canditate, unique_signs))
    print(cers)
    print(lowest_cer)

# test("Tow Away Signs Letters", ["TOW", "N-AWAY", "NO STOPPING", "4PM", "6PM", "EICEFT", "ST"])