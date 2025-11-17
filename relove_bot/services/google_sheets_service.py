"""
Сервис для работы с Google Sheets API.
"""
import os
from typing import List, Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GoogleSheetsService:
    """Сервис для работы с Google Sheets."""
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self, credentials_path: Optional[str] = None):
        """Инициализирует сервис Google Sheets."""
        self.credentials_path = credentials_path or os.getenv('GOOGLE_CREDENTIALS_PATH')
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Аутентифицируется в Google API."""
        if not self.credentials_path:
            raise ValueError("GOOGLE_CREDENTIALS_PATH не установлен в .env")
        
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(f"Файл учётных данных не найден: {self.credentials_path}")
        
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=self.SCOPES
            )
            self.service = build('sheets', 'v4', credentials=credentials)
        except Exception as e:
            raise Exception(f"Ошибка при аутентификации в Google Sheets: {e}")
    
    def get_sheet_id(self, spreadsheet_id: str, sheet_name: str) -> Optional[int]:
        """Получает ID листа по названию."""
        try:
            result = self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            for sheet in result.get('sheets', []):
                if sheet['properties']['title'] == sheet_name:
                    return sheet['properties']['sheetId']
            available_sheets = [sheet['properties']['title'] for sheet in result.get('sheets', [])]
            print(f"Доступные листы: {', '.join(available_sheets)}")
            return None
        except HttpError as e:
            print(f"Ошибка при получении ID листа: {e}")
            return None
    
    def create_sheet(self, spreadsheet_id: str, sheet_name: str) -> Optional[int]:
        """Создает новый лист в таблице."""
        try:
            requests = [{"addSheet": {"properties": {"title": sheet_name}}}]
            body = {'requests': requests}
            result = self.service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
            if result.get('replies'):
                return result['replies'][0]['addSheet']['properties']['sheetId']
            return None
        except HttpError as e:
            print(f"Ошибка при создании листа: {e}")
            return None
    
    def duplicate_sheet(self, spreadsheet_id: str, source_sheet_id: int, new_sheet_name: str) -> Optional[int]:
        """Дублирует лист (копирует весь лист с данными и форматированием)."""
        try:
            requests = [{"duplicateSheet": {"sourceSheetId": source_sheet_id, "newSheetName": new_sheet_name}}]
            body = {'requests': requests}
            result = self.service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
            if result.get('replies'):
                return result['replies'][0]['duplicateSheet']['properties']['sheetId']
            return None
        except HttpError as e:
            print(f"Ошибка при дублировании листа: {e}")
            return None
    
    def insert_image_with_text(self, spreadsheet_id: str, sheet_name: str, row_index: int, col_index: int, image_url: str, text: str) -> bool:
        """Вставляет изображение как фон ячейки с текстом поверх."""
        try:
            sheet_id = self.get_sheet_id(spreadsheet_id, sheet_name)
            if sheet_id is None:
                return False
            requests = [{
                "updateCells": {
                    "range": {"sheetId": sheet_id, "rowIndex": row_index, "columnIndex": col_index, "endRowIndex": row_index + 1, "endColumnIndex": col_index + 1},
                    "rows": [{"values": [{"userEnteredValue": {"stringValue": text}, "userEnteredFormat": {"backgroundImage": {"sourceUrl": image_url}, "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}, "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"}}]}],
                    "fields": "userEnteredValue,userEnteredFormat"
                }
            }]
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
            return True
        except HttpError as e:
            print(f"Ошибка при вставке изображения с текстом: {e}")
            return False
    
    def apply_pastel_colors(self, spreadsheet_id: str, sheet_name: str, num_rows: int, color_index: int = 0) -> bool:
        """Применяет пастельные цвета к листу (разные для каждого ритуала)."""
        try:
            sheet_id = self.get_sheet_id(spreadsheet_id, sheet_name)
            if sheet_id is None:
                return False
            pastel_colors = [
                {"red": 0.95, "green": 0.92, "blue": 0.98},
                {"red": 0.92, "green": 0.98, "blue": 0.95},
                {"red": 0.98, "green": 0.93, "blue": 0.90},
                {"red": 0.98, "green": 0.93, "blue": 0.95},
                {"red": 0.93, "green": 0.95, "blue": 0.98},
            ]
            bg_color = pastel_colors[color_index % len(pastel_colors)]
            header_color = {"red": 0.4, "green": 0.2, "blue": 0.6}
            requests = [
                {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 6}, "cell": {"userEnteredFormat": {"backgroundColor": header_color, "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}, "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"}}, "fields": "userEnteredFormat"}},
                {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": num_rows, "startColumnIndex": 0, "endColumnIndex": 6}, "cell": {"userEnteredFormat": {"backgroundColor": bg_color}}, "fields": "userEnteredFormat.backgroundColor"}}
            ]
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
            return True
        except HttpError as e:
            print(f"Ошибка при применении цветов: {e}")
            return False
    
    def update_rows_preserve_format(self, spreadsheet_id: str, sheet_name: str, rows: List[List[Any]]) -> bool:
        """Перезаписывает данные в таблице, сохраняя форматирование."""
        try:
            sheet_id = self.get_sheet_id(spreadsheet_id, sheet_name)
            if sheet_id is None:
                print(f"Лист '{sheet_name}' не найден")
                return False
            body = {'values': rows}
            self.service.spreadsheets().values().update(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!A1", valueInputOption='USER_ENTERED', body=body).execute()
            self._set_text_wrapping(spreadsheet_id, sheet_name, len(rows))
            return True
        except HttpError as e:
            print(f"Ошибка при обновлении строк в Google Sheets: {e}")
            return False
    
    def _set_text_wrapping(self, spreadsheet_id: str, sheet_name: str, num_rows: int) -> bool:
        """Устанавливает перенос текста, высоту строк и цветное оформление в палитре reLove."""
        try:
            sheet_id = self.get_sheet_id(spreadsheet_id, sheet_name)
            if sheet_id is None:
                return False
            header_color = {"red": 0.4, "green": 0.2, "blue": 0.6}
            light_bg = {"red": 0.95, "green": 0.92, "blue": 0.98}
            requests = [
                {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": num_rows, "startColumnIndex": 0, "endColumnIndex": 6}, "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}}, "fields": "userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment"}},
                {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 6}, "cell": {"userEnteredFormat": {"backgroundColor": header_color, "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}, "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"}}, "fields": "userEnteredFormat"}},
                {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": num_rows, "startColumnIndex": 0, "endColumnIndex": 6}, "cell": {"userEnteredFormat": {"backgroundColor": light_bg}}, "fields": "userEnteredFormat.backgroundColor"}},
                {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 1, "endIndex": num_rows}, "properties": {"pixelSize": 200}, "fields": "pixelSize"}},
                {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 50}, "fields": "pixelSize"}}
            ]
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
            return True
        except HttpError as e:
            print(f"Ошибка при установке переноса текста: {e}")
            return False
