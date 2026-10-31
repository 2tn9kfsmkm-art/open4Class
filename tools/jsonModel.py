import json


class JsonDataModel:
    def __init__(self, origin:str):
        self.origin = origin
        self.update()

    def __getattribute__(self, name:str):
        if name in ['origin', 'data', 'update']:
            return super().__getattribute__(name)
        return self.data[name]
    
    def __setattr__(self, name, value):
        if name == 'origin' or name == 'data':
            super().__setattr__(name, value)
        else:
            self.update(**{name:value})

    def update(self, **kwargs):
        if len(kwargs):
            self.data.update(kwargs)
            with open(self.origin, 'w') as f:
                json.dump(self.data, f)
        else:
            with open(self.origin, 'r') as f:
                self.data = json.load(f)
