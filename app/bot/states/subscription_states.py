from aiogram.fsm.state import State, StatesGroup

 
class SubscriptionStates(StatesGroup):
    WAITING_FOR_PROMOCODE = State() 