"""
pyley Python client for an open-source graph database Cayley

:copyright: (c) 2014 by Ziya SARIKAYA @ziyasal.
:license: MIT, see LICENSE for more details.

"""
import json

import requests

__title__ = 'pyley'
__version__ = '0.1.1-dev'
__author__ = 'Ziya SARIKAYA @ziyasal'
__license__ = 'MIT'
__copyright__ = 'Copyright 2014 Ziya SARIKAYA @ziyasal'


class NotAValidQuadError(Exception):
    pass


class CayleyResponse(object):
    def __init__(self, raw_response, result):
        self.r = raw_response
        self.result = result


class CayleyQuad(object):
    """
    :type subject: str
    :type predicate: str
    :type object: str
    :type label: str
    """

    def __init__(self, subject, predicate, object, label=None):
        """
        :type subject: str
        :type predicate: str
        :type object: str
        :type label: str
        """
        self.subject = self._clean(subject)
        self.predicate = self._clean(predicate)
        self.object = self._clean(object)
        self.label = self._clean(label)

    @staticmethod
    def _clean(obj):
        """
        :type obj: str
        """
        return obj.strip().replace(' ', '_').lower() if obj is not None else None

    def to_dict(self):
        r = {'subject': self.subject, 'predicate': self.predicate, 'object': self.object}
        if self.label is not None:
            r['label'] = self.label
        return r

    def to_json(self):
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, obj):
        try:
            return cls(**obj)
        except TypeError:
            raise NotAValidQuadError()

    @classmethod
    def from_json(cls, obj):
        try:
            return cls.from_dict(json.loads(obj))
        except ValueError:
            raise NotAValidQuadError()

    def __eq__(self, other):
        if not isinstance(other, CayleyQuad):
            try:
                other = CayleyQuad.from_dict(other)
            except NotAValidQuadError:
                try:
                    other = CayleyQuad.from_json(other)
                except NotAValidQuadError:
                    return False
        return (
            self.subject == other.subject and
            self.predicate == other.predicate and
            self.object == other.object and
            self.label == other.label
        )

    def __hash__(self):
        return (
            3 * self.subject.__hash__() +
            5 * self.predicate.__hash__() +
            7 * self.object.__hash__() +
            11 * self.label.__hash__()
        )

    def __str__(self):
        return self.to_json()


class CayleyQuads(object):
    """
    :type quads: set[CayleyQuad]
    """

    def __init__(self, quads=None):
        """
        :type quads: set[CayleyQuad]
        """
        self.quads = quads if quads is not None else []

    def add_quad(self, quad):
        self.quads.add(quad)

    def add_quads(self, quads):
        self.quads | set(quads)

    def to_json(self):
        return json.dumps([quad.to_dict() for quad in self.quads])

    @classmethod
    def from_list(cls, obj):
        return cls(quads={CayleyQuad.from_dict(quad) for quad in obj})

    @classmethod
    def from_json(cls, obj):
        return cls.from_list(json.loads(obj))

    def __str__(self):
        return self.to_json()


class CayleyClient(object):
    def __init__(self, url="http://localhost:64210", version="v1"):
        self.query_url = "%s/api/%s/query/gremlin" % (url, version)
        self.write_url = "%s/api/%s/write" % (url, version)

    def Send(self, query):
        if isinstance(query, str):
            r = requests.post(self.query_url, data=query)
            return CayleyResponse(r, r.json())
        elif isinstance(query, _GremlinQuery):
            r = requests.post(self.query_url, data=str(query))
            return CayleyResponse(r, r.json())
        else:
            raise Exception("Invalid query parameter in Send")

    def Write(self, quads):
        """
        :type quads: CayleyQuads
        """
        r = requests.post(self.write_url, data=quads.to_json())
        return r.content


class _GremlinQuery(object):
    queryDeclarations = None

    def __init__(self):
        self.queryDeclarations = []

    def __str__(self):
        return ".".join([str(d) for d in self.queryDeclarations])

    def _put(self, token, *parameters):
        q = _QueryDefinition(token, *parameters)
        self.queryDeclarations.append(q)


class GraphObject(object):
    def V(self):
        return _Vertex("g.V()")

    def V(self, *node_ids):
        builder = []
        l = len(node_ids)
        for index, node_id in enumerate(node_ids):
            if index == l - 1:
                builder.append(u"'{0:s}'".format(node_id))
            else:
                builder.append(u"'{0:s}',".format(node_id))

        return _Vertex(u"g.V({0:s})".format("".join(builder)))

    def M(self):
        return _Morphism("g.Morphism()")

    def Vertex(self):
        return self.V()

    def Vertex(self, *node_ids):
        if len(node_ids) == 0:
            return self.V()

        return self.V(node_ids)

    def Morphism(self):
        return self.M()

    def Emit(self, data):
        return "g.Emit({0:s})".format(json.dumps(data, default=lambda o: o.__dict__))


class _Path(_GremlinQuery):
    def __init__(self, parent):
        _GremlinQuery.__init__(self)
        self._put(parent)

    def Out(self, predicate=None, tags=None):
        self._bounds("Out", predicate, tags)

        return self

    def In(self, predicate=None, tags=None):
        self._bounds("In", predicate, tags)

        return self

    def Both(self, predicate=None, tags=None):
        self._bounds("Both", predicate, tags)

        return self

    def _bounds(self, method, predicate=None, tags=None):
        if predicate is None and tags is None:
            self._put("%s()", method)
        elif tags is None:
            self._put("%s(%s)", method, self._format_input_bounds(predicate))
        else:
            self._put(
                "%s(%s, %s)",
                method,
                self._format_input_bounds(predicate),
                self._format_input_bounds(tags)
            )

        return self

    def _format_input_bounds(self, value):
        if type(value) is dict:
            return json.dumps(value)

        if type(value) is str:
            return "'%s'" % value

        if value is None:
            return 'null'

        return value

    def Is(self, *nodes):
        self._put("Is('%s')", "', '".join(nodes))

        return self

    def Has(self, predicate, object):
        self._put("Has('%s', '%s')", predicate, object)

        return self

    def Tag(self, *tags):
        self._put("Tag(%s)", json.dumps(tags))

        return self

    def Back(self, tag):
        self._put("Back('%s')", tag)

        return self

    def Save(self, predicate, tag):
        self._put("Save('%s', '%s')", predicate, tag)

        return self

    def Intersect(self, query):
        if not isinstance(query, _Vertex) and type(query) is not str:
            raise Exception("Invalid parameter in intersect query")

        self._put("Intersect(%s)", query)

        return self

    def Union(self, query):
        if not isinstance(query, _Vertex) and type(query) is not str:
            raise Exception("Invalid parameter in union query")

        self._put("Union(%s)", query)

        return self

    def Follow(self, query):
        if not isinstance(query, _Morphism) and type(query) is not str:
            raise Exception("Invalid parameter in follow query")

        self._put("Follow(%s)", query)

        return self

    def FollowR(self, query):
        if not isinstance(query, _Morphism) and type(query) is not str:
            raise Exception("Invalid parameter in followr query")

        self._put("FollowR(%s)", query)

        return self

    def build(self):
        return str(self)


class _Vertex(_Path):
    def All(self):
        self._put("All()")

        return self

    def GetLimit(self, limit):
        self._put("GetLimit(%d)", limit)

        return self


class _Morphism(_Path):
    pass


class _QueryDefinition(object):
    def __init__(self, token, *parameters):
        self.token = token
        self.parameters = parameters

    def __str__(self):
        if len(self.parameters) > 0:
            return str(self.token) % self.parameters
        else:
            return str(self.token)
