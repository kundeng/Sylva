# -*- coding: utf-8 -*-
import parsley


class Counter(dict):

    def __init__(self, *args, **kwargs):
        super(Counter, self).__init__(*args, **kwargs)
        self.types = dict()

    def get(self, type, default=None):
        if default and type not in self.types:
            return default
        self.types.setdefault(type, -1)
        self.types[type] += 1
        return self.types[type]


class QueryParser(object):

    def __init__(self, graph):
        self.graph = graph
        self.schema = graph.schema
        self.counter = Counter()
        self.r_types = {}
        self.n_types = {}

    def parse(self, query):
        grammar = self.build_grammar()
        grammar_query = grammar(query)
        query_dict = grammar_query.dict()
        import pprint
        pprint.pprint(query_dict)
        return query_dict

    def build_grammar(self):

        def merge(*args):
            """Merge dictionaries in *args"""
            m = {}
            for key in ("conditions", "origins", "patterns", "results"):
                m[key] = []
                for d in args:
                    m[key] += d.get(key, [])
            return m

        def node_facet(f=None, t=None, p=None, v=None, r=None, **kwargs):
            if not t:
                return {}
            elif f and p and v:
                if r:
                    return {
                        'conditions': [(f, ('property', t['alias'], p), v)],
                        'origins': [t],
                        'results': [{
                            "alias": t['alias'], "properties": r
                        }]}
                else:
                    return {
                        'conditions': [(f, ('property', t['alias'], p), v)],
                        'origins': [t],
                        'results': [{
                            "alias": t['alias'], "properties": None
                        }]}
            else:
                if r:
                    return {
                        'conditions': [],
                        'origins': [t],
                        'results': [{
                            "alias": t['alias'], "properties": r
                        }]}
                else:
                    return {
                        'conditions': [],
                        'origins': [t],
                        'results': [{
                            "alias": t['alias'], "properties": None
                        }]}

        self.counter = Counter()
        self.r_types = {}
        self.n_types = {}
        node_type_rules = self.get_node_type_rules()
        relationship_type_rules = self.get_relationship_type_rules()
        rules = [u"""
n_facet = ('with' (ws ('a' | 'the'))?)
        -> ""
r_facet = ('that' | 'who')
        -> ""
conditions = "and"
           -> "and"
           | "or"
           -> "or"
           | -> "and"
op = ("that" ws "start" "s"? ws "with" ws)
   -> 'istartswith'
   | ("that" ws "end" "s"? ws "with" ws)
   -> 'iendswith'
   | ("greater" ws "than" ws)
   -> 'gt'
   | ("lower" ws "than" ws)
   -> 'lt'
   | -> 'iexact'
        """]
        rules += node_type_rules
        rules += relationship_type_rules
        rules += [u"""
rel = <r_types:r> ws <n_types:t>
    -> {'relation': r, 'node': t, 'merge': merge(r, t)}
    | -> {}

dict = <n_types:n> <~rel>
     -> n
     | <n_types:s> ws <rel:r>
     -> merge(s, r['merge'], {"patterns": [{
            "source": s["origins"][-1],  # Not sure if [0] or [-1]
            "target": r["node"]["origins"][-1],
            "relation": r["relation"]["origins"][-1],
        }]})
     | -> None
        """]
        rules = u"\n".join(rules)
        print rules
        return parsley.makeGrammar(rules, {
            "merge": merge,
            "r_types": self.r_types,
            "n_types": self.n_types,
            "counter": self.counter,
            "node_facet": node_facet,
        })

    def get_relationship_type_rules(self):
        rules = []

        rel_type_rule_codes = []
        rules_template = u"""
r{rel_type_id} = ('{rel_type_names}')
        -> {{'type_id': r_types.get({rel_type_id}), 'type': 'relationship',  'alias': "r{rel_type_id}_{{0}}".format(counter.get('r{rel_type_id}', 0))}}
r{rel_type_id}_facet = (conditions ws)? r_facet ws <r{rel_type_id}:r> ws ("a" | "the")?
        -> {{'origins': [r], 'results': [{{"alias": r['alias'], "properties": []}}]}}
        """
        rel_types = self.schema.relationshiptype_set.all().select_related()
        for rel_type in rel_types:
            # We can put rel_type (withouth the .id) if we want to send
            # the actual RelationshipType object
            self.r_types[rel_type.id] = rel_type.id
            rel_type_rule_codes.append(u"r{0}_facet".format(rel_type.id))
            properties = []
            for prop in rel_type.properties.all().values("key"):
                property_name = prop["key"]
                property_names = [
                    property_name,
                    property_name.lower(),
                    property_name.upper(),
                    property_name.capitalize(),
                    u"{0}s".format(property_name),
                    u"{0}s".format(property_name).lower(),
                    u"{0}s".format(property_name).upper(),
                    u"{0}s".format(property_name).capitalize()
                ]
                rule = u"('{0}') -> u'{1}'"
                property_rule = rule.format(
                    u"' | '".join(property_names),
                    property_name
                )
                properties.append(property_rule)
            rel_type_names = [rel_type.name, rel_type.name.lower(),
                              rel_type.name.upper(),
                              rel_type.name.capitalize()]
            if rel_type.plural_name:
                rel_type_names += [rel_type.plural_name,
                                   rel_type.plural_name.lower(),
                                   rel_type.plural_name.upper(),
                                   rel_type.plural_name.capitalize()]
            else:
                rel_type_names += [u"{0}s".format(rel_type.name),
                                   u"{0}s".format(rel_type.name).lower(),
                                   u"{0}s".format(rel_type.name).upper(),
                                   u"{0}s".format(rel_type.name).capitalize()]
            rel_type_rules = rules_template.format(
                rel_type_id=rel_type.id,
                rel_type_names=u"' | '".join(rel_type_names),
                rel_type_properties=u"\n    | ".join(properties),
            )
            rules.append(rel_type_rules)
        rule = u"r_types = ({0})"
        rules.append(rule.format(u" | ".join(rel_type_rule_codes)))
        return rules

    def get_node_type_rules(self):
        rules = []
        node_type_rule_codes = []
        rules_template = u"""
n{node_type_id}_value = <anything*:x> -> ''.join(x)
n{node_type_id} = ('{node_type_names}')
       -> {{'type_id': n_types.get({node_type_id}), 'type': 'node', 'alias': "n{node_type_id}_{{0}}".format(counter.get('n{node_type_id}', 0))}}
n{node_type_id}_property = {node_type_properties}
n{node_type_id}_properties = <n{node_type_id}_property:first> <(ws (',' | "and") ws n{node_type_id}_property)*:rest>
        -> [first] + rest
        | -> []
n{node_type_id}_facet = (<n{node_type_id}_properties:r> ws ("of" | "from") ws ("the" ws)?)? <n{node_type_id}:t> <(ws <n_facet> ws <n{node_type_id}_property:p> "of"? ws <op?:f> ws <n{node_type_id}_value:v>)?>
        -> node_facet(**locals())
        # Conditions
        | <n{node_type_id}_facet:left> ws <conditions:cond> ws <n{node_type_id}_facet:right>
        -> (cond, left, right)
        """
        for node_type in self.schema.nodetype_set.all().select_related():
            # We can put node_type (withouth the .id) if we want to send
            # the actual NodeType object
            self.n_types[node_type.id] = node_type.id
            node_type_rule_codes.append(u"n{0}_facet".format(node_type.id))
            properties = []
            for prop in node_type.properties.all().values("key"):
                property_name = prop["key"]
                property_names = [
                    property_name,
                    property_name.lower(),
                    property_name.upper(),
                    property_name.capitalize(),
                    u"{0}s".format(property_name),
                    u"{0}s".format(property_name).lower(),
                    u"{0}s".format(property_name).upper(),
                    u"{0}s".format(property_name).capitalize()
                ]
                rule = u"('{0}') -> u'{1}'"
                property_rule = rule.format(
                    u"' | '".join(property_names),
                    property_name
                )
                properties.append(property_rule)
            node_type_names = [node_type.name, node_type.name.lower(),
                               node_type.name.upper(),
                               node_type.name.capitalize()]
            if node_type.plural_name:
                node_type_names += [node_type.plural_name,
                                    node_type.plural_name.lower(),
                                    node_type.plural_name.upper(),
                                    node_type.plural_name.capitalize()]
            else:
                node_type_names += [u"{0}s".format(node_type.name),
                                    u"{0}s".format(node_type.name).lower(),
                                    u"{0}s".format(node_type.name).upper(),
                                    u"{0}s".format(node_type.name).capitalize()]
            node_type_rules = rules_template.format(
                node_type_id=node_type.id,
                node_type_names=u"' | '".join(node_type_names),
                node_type_properties=u"\n    | ".join(properties),
            )
            rules.append(node_type_rules)
        rule = u"n_types = ({0})"
        rules.append(rule.format(" | ".join(node_type_rule_codes)))
        return rules
