from . import FilterParser


class MongoDbFilterParser(FilterParser):

    @staticmethod
    def mongo_unary(op: str):
        def gen(a):
            return {op: a}

        return gen

    @staticmethod
    def mongo_binary_op(op: str):
        def gen(a, b):
            return {a: {op: b}}

        return gen

    @staticmethod
    def mongo_multi_op(op: str):
        def gen(*args):
            return {op: list(args)}

        return gen

    func_map = {
        'length': mongo_unary('$strLenCP'),
        'indexOf': mongo_unary('$indexOfCP'),
        'replace': mongo_multi_op('$replaceAll'),
        'substring': mongo_multi_op('$substrBytes'),
        'toLower': mongo_unary('$toLower'),
        'toUpper': mongo_unary('$toUpper'),
        'trim': mongo_unary('$trim'),
        'round': mongo_unary('$round'),
        'floor': mongo_unary('$floor'),
        'ceiling': mongo_unary('$ceil'),
        'year': mongo_unary('$year'),
        'month': mongo_unary('$month'),
        'day': mongo_unary('$day'),
        'hour': mongo_unary('$hour'),
        'minute': mongo_unary('$minute'),
        'second': mongo_unary('$second'),
    }

    op_map = {
        'eq': mongo_binary_op('$eq'),
        'ne': mongo_binary_op('$ne'),
        'gt': mongo_binary_op('$gt'),
        'lt': mongo_binary_op('$lt'),
        'ge': mongo_binary_op('$gte'),
        'le': mongo_binary_op('$lte'),
        'add': mongo_binary_op('$add'),
        'sub': mongo_binary_op('$subtract'),
        'mul': mongo_binary_op('$multiply'),
        'div': mongo_binary_op('$divide'),
        'mod': mongo_binary_op('$mod'),
        'AND': mongo_multi_op('$and'),
        'OR': mongo_multi_op('$or'),
        'like': lambda a, b: {a: {'$regex': b, '$options': 'i'}},
        'endswith': lambda a, b: {a: {'$regex': b + '$', '$options': 'i'}},
        'startswith': lambda a, b: {a: {'$regex': '^' + b, '$options': 'i'}},
        'contains': mongo_binary_op('$in'),
        'lacks': mongo_binary_op('$nin'),
        'has': lambda a, b: {a: {'$elemMatch': {'$eq': b}}},
        'hasNot': lambda a, b: {'$not': {a: {'$elemMatch': {'$eq': b}}}},
    }

    def __init__(self):
        super().__init__(op_map=self.op_map, func_map=self.func_map)

    def get_column(self, col: str):
        return col
