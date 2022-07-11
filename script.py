import logging
import os
import httplib2
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
import aiogram.utils.markdown as md
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode, BotCommand, ReplyKeyboardMarkup, CallbackQuery, Message
from aiogram.utils import executor
from aiogram_calendar import simple_cal_callback, SimpleCalendar, dialog_cal_callback, DialogCalendar
import firebase_admin
from firebase_admin import credentials, storage
from firebase_admin import firestore
from firebase_admin import db

logging.basicConfig(level=logging.INFO)

API_TOKEN = '5572595899:AAHgzD6Mf7hSkuQX4pMtO_BM_O8lPGfxAbU'

bot = Bot(token=API_TOKEN)

#firebase conf
cred = credentials.Certificate("secrets/botchelenge-firebase-adminsdk-l0l7c-47a0f4fa6f.json")
firebase_admin.initialize_app(cred, {
    'databaseURL':'https://botchelenge-default-rtdb.europe-west1.firebasedatabase.app/',
    'storageBucket': 'botchelenge.appspot.com'
})
db = firestore.client()

# For example use simple MemoryStorage for Dispatcher.
Memorystorage = MemoryStorage()
dp = Dispatcher(bot, storage=Memorystorage)

start_kb = ReplyKeyboardMarkup(resize_keyboard=True,)
start_kb.row('Navigation Calendar', 'Dialog Calendar')

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="/countStep", description="Зарегистрировать шаги"),
    ]
    await bot.set_my_commands(commands)

# States
class Form(StatesGroup):
    startState = State()
    fullName = State()  # Will be represented in storage as 'Form:name'
    dateTime = State()
    countStep = State()
    imageArtifact = State()

@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    """
    Conversation's entry point
    """
    # Set state
    await Form.startState.set()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add("Начать")
    await message.answer("Привет! Я чат-бот проекта «Diasoft Step challenge  – 2022». Присоединяйся к нам, вместе мы делаем доброе дело!", reply_markup=markup)

@dp.message_handler(state=Form.startState)
async def process_start(message: types.Message, state: FSMContext):
    # Update state and data
    markup = types.ReplyKeyboardRemove()
    users_ref = db.collection(u'users')
    docs = users_ref.stream()
    find_user = False
    for doc in docs:
        user = doc.to_dict()
        if doc.id == message.from_user.username:
            find_user = True
            current_user = user
    if find_user:
        async with state.proxy() as data:
            data['name'] = current_user['fullName']
        await Form.dateTime.set()
        await message.answer("Ты снова с нами, " + current_user['fullName'] + "!",
                             reply_markup=markup)
        await message.answer("Укажи день, за который ты вносишь результат?",
                             reply_markup=await SimpleCalendar().start_calendar())
    else:

        await message.answer("Пожалуйста, представься! Напиши Фамилию Имя Отчество", reply_markup=markup)
        await Form.next()

@dp.message_handler(state=Form.fullName)
async def process_name(message: Message, state: FSMContext):
    """
    Process user name
    """
    await Form.next()
    async with state.proxy() as data:
        data['name'] = message.text
    doc_ref = db.collection(u'users').document(message.from_user.username)
    doc_ref.set({
        u'fullName': data['name'],
    })
    await message.answer("Привет, " + data['name'] + "! Укажи день, за который ты вносишь результат?",  reply_markup= await SimpleCalendar().start_calendar())

# simple calendar usage
@dp.callback_query_handler(simple_cal_callback.filter(), state=Form.dateTime)
async def process_simple_calendar(callback_query: CallbackQuery, callback_data: dict, state: FSMContext):
    selected, date = await SimpleCalendar().process_selection(callback_query, callback_data)
    if selected:
        async with state.proxy() as data:
            data['date'] = date.strftime("%d/%m/%Y")
        await Form.next()
        await callback_query.message.answer(
            f'Пожалуйста, укажи количество пройденных шагов',
        )

# You can use state '*' if you need to handle all states
@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        return
    logging.info('Cancelling state %r', current_state)
    # Cancel state and inform user about it
    await state.finish()
    # And remove keyboard (just in case)
    await message.reply('Cancelled.', reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(lambda message: not message.text.isdigit(), state=Form.countStep)
async def process_count_invalid(message: types.Message, state: FSMContext):
    """
    If age is invalid
    """
    return await message.reply("Укажи,пожалуйста, числовые значения")

@dp.message_handler(lambda message: message.text.isdigit(), state=Form.countStep)
async def process_countstep(message: types.Message, state: FSMContext):
    # Update state and data
    if int(message.text) > 10000:
        await Form.next()
        await state.update_data(countStep=int(message.text))
        await message.answer("Пожалуйста, приложи подтверждающий скриншот" + " @" + str(message.from_user.username))
    else:
        await Form.startState.set()
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
        markup.add("Попробовать еще")
        await message.answer("Ты молодец, но в зачет идут 10 000+ шагов в день", reply_markup=markup)

@dp.message_handler(state=Form.imageArtifact, content_types=['photo'])
async def process_image(message: types.Message, state: FSMContext):
    await message.photo[-1].download('screen_'+message.photo[-1].file_unique_id +'.png')
    # Put your local file path
    fileName = 'screen_'+ message.photo[-1].file_unique_id +'.png'
    bucket = storage.bucket()
    blob = bucket.blob(fileName)
    blob.upload_from_filename(fileName)

    # Opt : if you want to make public access from the URL
    blob.make_public()
    if (os.path.isfile('screen_'+ message.photo[-1].file_unique_id +'.png')):

        # os.remove() function to remove the file
        os.remove('screen_'+ message.photo[-1].file_unique_id +'.png')

        # Printing the confirmation message of deletion
        print("File Deleted successfully")
    else:
        print("File does not exist")

    print("your file url", blob.public_url)
    async with state.proxy() as data:
        data['imageArtifact'] = blob.public_url

    async with state.proxy() as data:
        # data['name'] = "@" + message.from_user.username

        doc_ref = db.collection(u'users').document(message.from_user.username)
        doc_ref.set({
            u'fullName': data['name'],
            u'countStep': data['countStep'],
            u'dateTime': data['date'],
            u'imageArtifact': data['imageArtifact']
        })

        # And send message
        await bot.send_message(
            message.chat.id,
            md.text(
                md.text('Результат принят. Спасибо за вклад в «Доброе дело»!'),
                md.text('Дата:', md.code(data['date'])),
                md.text('Количество шагов:', data['countStep']),
                sep='\n',
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        # Запищем информацию в гугл шит
        service = get_service_sacc()
        sheet = service.spreadsheets()
        sheet_id = "1O8ey-FM3QwiYhCwj5DS7ERWsRmaQ8ze06Tu4J2CfwQM"

        body = {
            'values': [
                [data['name'], data['date'], data['countStep'], data['imageArtifact']],  # строка
            ]
        }

        sheet.values().append(
        spreadsheetId=sheet_id,
        range="Лист1!A2:L99",
        valueInputOption="RAW",
        body=body).execute()

    # Finish conversation
    await state.finish()
    await Form.startState.set()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add("Добавить шаги")
    await message.answer("Как будешь готов, приходи опять", reply_markup=markup)

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

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)