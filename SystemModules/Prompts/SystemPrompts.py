#ALL PROMPTS
#DESCRIBE_LETTER
#REPEAT_DESCRIPTION


#ANSWER
#CONFIRM
#DENY

#LEARN_MODE
#QUIZ_MODE
#OBJECT_DETECTION
#DISTANCE_CHECK

#GREET
#CANCEL
#STATE_MODE
#TIME_QUERY
#DATE_QUERY

EDUCATION_PROMPT_MAP = {
    "what letter is this": "DESCRIBE_LETTER",
    "describe this": "DESCRIBE_LETTER",
    "repeat that": "REPEAT_DESCRIPTION",
    "what's this": "DESCRIBE_LETTER",
    "cancel": "CANCEL",
    "exit": "CANCEL"
}

QUIZ_PROMPT_MAP = {
    "it's a": "ANSWER",
    "i think it's": "ANSWER",
    "yes" : "CONFIRM",
    "no" : "DENY",
    "cancel": "CANCEL",
    "exit": "CANCEL"
}

MAIN_PROMPT_MAP = {
    "teach me braille": "LEARN_MODE",
    "start quiz": "QUIZ_MODE",
    "detect objects": "OBJECT_DETECTION",
    "check distance": "DISTANCE_CHECK",
    "cancel": "CANCEL"
}

COMMON_PROMPT_MAP = {
    "hi" : "GREET",
    "hello" : "GREET",
    "hey" : "GREET",
    "hello again" : "GREET",
    "greetings" : "GREET",
    "hello there" : "GREET",
    "what is my current mode:" : "STATE_MODE",
    "time now" : "TIME_QUERY",
    "what time is it" : "TIME_QUERY",
    "current time" : "TIME_QUERY",
    "time right now" : "TIME_QUERY",
    "current date" : "DATE_QUERY",
    "date today" : "DATE_QUERY"
}