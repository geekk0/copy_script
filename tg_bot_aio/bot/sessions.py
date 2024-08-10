

class Session:
    mode = None
    studio = None
    path = '/cloud/reflect/files'
    month_selected = False
    date_selected = False
    time_selected = False

    def __init__(self, mode):
        self.mode = mode