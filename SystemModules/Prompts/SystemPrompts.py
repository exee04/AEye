EDUCATION_PROMPT_MAP = {
    "what letter is this": "DESCRIBE_LETTER",
    "describe this": "DESCRIBE_LETTER",
    "repeat that": "REPEAT_DESCRIPTION",
    "what's this": "DESCRIBE_LETTER",
    "cancel": "CANCEL",
    "exit": "CANCEL",
    "help me": "SHOW_HELP",
    "what is my current mode:" : "STATE_MODE"
}

QUIZ_PROMPT_MAP = {
    "it's a": "ANSWER",
    "i think it's": "ANSWER",
    "cancel": "CANCEL",
    "help me": "SHOW_HELP",
    "exit": "CANCEL",
    "what is my current mode:" : "STATE_MODE"
}

MAIN_PROMPT_MAP = {
    "teach me braille": "LEARN_MODE",
    "start quiz": "QUIZ_MODE",
    "detect objects": "OBJECT_DETECTION",
    "check distance": "DISTANCE_CHECK",
    "cancel": "CANCEL",
    "help me": "SHOW_HELP",
    "what is my current mode:" : "STATE_MODE"
}