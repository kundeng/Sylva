    # -*- coding: utf-8 -*-
from collections import Sequence
from datetime import datetime
import random

from django.db import transaction

from engines.gdb.backends import NodeDoesNotExist, RelationshipDoesNotExist
from schemas.models import NodeType, RelationshipType


ASC = "asc"
DESC = "desc"


class LimitReachedException(Exception):
    pass


class NodesLimitReachedException(LimitReachedException):
    pass


class RelationshipsLimitReachedException(LimitReachedException):
    pass


class GraphMixin(object):

    ASC = ASC
    DESC = DESC

    def __init__(self, *args, **kwargs):
        super(GraphMixin, self).__init__(*args, **kwargs)
        self._q = None
        self._gdb = None
        self._nodes_manager = None
        self._relationships_manager = None
        self._analysis_manager = None

    def _get_gdb(self):
        if not self._gdb:
            self._gdb = self.data.get_gdb()
        return self._gdb
    gdb = property(_get_gdb)

    def _get_nodes(self):
        if not self._nodes_manager:
            self._nodes_manager = NodesManager(self)
        return self._nodes_manager
    nodes = property(_get_nodes)

    def _get_relationships(self):
        if not self._relationships_manager:
            self._relationships_manager = RelationshipsManager(self)
        return self._relationships_manager
    relationships = property(_get_relationships)

    def _get_analysis(self):
        if not self._analysis_manager:
            from analytics.models import AnalysisManager
            self._analysis_manager = AnalysisManager(self)
        return self._analysis_manager
    analysis = property(_get_analysis)

    def _get_q(self):
        if not self._q:
            gdb = self.gdb
            if hasattr(gdb, "lookup_builder"):
                self._q = gdb.lookup_builder()
            else:
                raise NotImplementedError("Q objects not implemented")
        return self._q
    Q = property(_get_q)

    def query(self, query_dict, order_by=None, headers=None, only_ids=None):
        return self.gdb.query(query_dict, order_by=order_by,
                              headers=headers, only_ids=only_ids)

    def destroy(self):
        """Delete nodes, relationships, internal indices, data, schema and
        the object itself"""
        self.gdb.destroy()
        self.schema.delete()
        self.data.delete()
        self.delete()


class BaseManager(object):

    def __init__(self, graph):
        self.graph = graph
        self.gdb = graph.gdb
        # self.schema = (not graph.relaxed) and graph.schema
        self.schema = graph.schema
        self.data = graph.data

    def _filter_dict(self, properties, itemtype):
        if properties:
            if self.schema:
                property_keys = [p.key for p in itemtype.properties.all()]
                popped = [properties.pop(k) for k in properties.keys()
                                            if (k not in property_keys
                                                or unicode(k).startswith("_"))]
                del popped
                return properties
            else:
                return dict(filter(lambda (k, v):
                                       not unicode(k).startswith("_"),
                                       properties.iteritems()))
        else:
            return {}

    def get(self, node_id, *args, **kwargs):
        try:
            return self._get(node_id)
        except KeyError:
            if args:
                return args[0]
            elif "default" in kwargs:
                return kwargs["default"]
            else:
                raise KeyError(node_id)


class BaseSequence(Sequence):

    def __init__(self, graph, iterator_func, *args, **kwargs):
        self.graph = graph
        self.func = iterator_func
        self.args = args
        self.kwargs = kwargs
        self.elements = None

    def __len__(self):
        if not self.elements:
            eltos = self.func(*self.args, **self.kwargs)
            self.elements = self.create_list(eltos, with_labels=True)
        return len(self.elements)

    def __getitem__(self, key):
        if isinstance(key, (int, float, long)):
            if not self.elements:
                eltos = self.func(*self.args, **self.kwargs)
                self.elements = self.create_list(eltos, with_labels=True)
            return self.elements[key]
        elif isinstance(key, slice):
            if not self.elements:
                self.kwargs.update({
                    "offset": key.start or 0,
                    "limit": (key.start or 0) + (key.stop or 1),
                })
                eltos = self.func(*self.args, **self.kwargs)
                return self.create_list(eltos, with_labels=True)[:]
            return self.elements[key]
        else:
            raise TypeError("key must be a number or a slice")

    def order_by(self, *orders):
        """
        Allow chaining order by to both NodeSequence and RelationshipSequence
        :param orders: list of mixed 2-tuples, like ('property_name', ASC|DESC),
                       and single property names (sorted ascending),
                       like 'property_name'.
        """
        orders_by = []
        for order in orders:
            order_method = ASC
            if isinstance(order, (list, tuple)):
                property_name, order_method = order
                if order_method not in (ASC, DESC):
                    order_method = ASC
            else:
                property_name = order
            orders_by.append((property_name, order_method))
        self.kwargs.update({
            "order_by": orders_by,
        })
        return self


class NodeSequence(BaseSequence):

    def create_list(self, eltos, with_labels=False):
        nodes = []
        if with_labels:
            for node_id, node_properties, node_label in eltos:
                node = Node(node_id, self.graph, initial=node_properties,
                            label=node_label)
                nodes.append(node)
        else:
            for node_id, node_properties in eltos:
                node = Node(node_id, self.graph, initial=node_properties)
                nodes.append(node)
        return nodes


class NodesManager(BaseManager):
    NodeDoesNotExist = NodeDoesNotExist

    def create(self, label, properties=None):
        if self.data.can_add_nodes():
            with transaction.atomic():
                if self.schema:
                    nodetype = self.schema.nodetype_set.get(pk=label)
                    if not self.graph.relaxed:
                        properties = self._filter_dict(properties, nodetype)
                    nodetype.total += 1
                    nodetype.save()
                self.data.total_nodes += 1
                self.data.last_modified_nodes = datetime.now()
                self.data.save()
            node_id = self.gdb.create_node(label=label, properties=properties)
            node = Node(node_id, self.graph, initial=properties, label=label)
            return node
        else:
            raise NodesLimitReachedException

    def all(self):
        node_types = self.graph.schema.nodetype_set.all()
        node_labels = [str(node_type.id) for node_type in node_types]
        return NodeSequence(graph=self.graph,
                            iterator_func=self.gdb.get_filtered_nodes,
                            lookups=None,
                            label=node_labels,
                            include_properties=True)

    def filter(self, *lookups, **options):
        if "label" in options:
            label = options.get("label")
            if not lookups:
                eltos = NodeSequence(graph=self.graph,
                                     iterator_func=self.gdb.get_nodes_by_label,
                                     label=label, include_properties=True)
            else:
                eltos = NodeSequence(graph=self.graph,
                                     iterator_func=self.gdb.get_filtered_nodes,
                                     lookups=lookups,
                                     label=label,
                                     include_properties=True)
        else:
            eltos = NodeSequence(graph=self.graph,
                                 lookups=lookups,
                                 iterator_func=self.gdb.get_filtered_nodes,
                                 include_properties=True)
        # We call __len__() to create the list of elements
        # eltos.__len__()
        return eltos

    def iterator(self):
        eltos = self.gdb.get_all_nodes(include_properties=True)
        for node_id, node_properties, node_label in eltos:
            node = Node(node_id, self.graph, initial=node_properties,
                        label=node_label)
            yield node

    def in_bulk(self, id_list):
        nodes = []
        eltos = self.gdb.get_nodes_properties(id_list)
        for node_id, node_properties in eltos:
            node = Node(node_id, self.graph, initial=node_properties)
            nodes.append(node)
        return nodes

    def delete(self, **options):
        if "label" in options:
            label = options.get("label")
            eltos = self.gdb.get_nodes_by_label(label, include_properties=False)
            nodes_id = []
            for node_id, n_props, n_label in eltos:
                for relationship in self.get(node_id).relationships.all():
                    relationship.delete()
                nodes_id.append(node_id)
            count = self.gdb.delete_nodes(nodes_id)
            with transaction.atomic():
                self.data.total_nodes -= count
                self.data.last_modified_nodes = datetime.now()
                self.data.save()
                if self.schema:
                    schema = self.schema
                    nodetype = schema.nodetype_set.get(pk=label)
                    nodetype.total = 0
                    nodetype.save()
        elif "id" in options:
            node_ids = options.get("id")
            if isinstance(node_ids, (list, tuple)):
                node_ids = list(node_ids)
            for node_id in node_ids:
                Node(node_id, self.graph).delete()
        else:
            eltos = self.gdb.get_all_nodes(include_properties=False)
            self.gdb.delete_nodes([node_id
                                   for node_id, n_props, n_label in eltos])
            with transaction.atomic():
                self.data.total_relationships = 0
                self.data.total_nodes = 0
                now = datetime.now()
                self.data.last_modified_nodes = now
                self.data.last_modified_relationships = now
                self.data.save()
                if self.schema:
                    schema = self.schema
                    for nodetype in schema.nodetype_set.all():
                        nodetype.total = 0
                        nodetype.save()
                    for reltype in schema.relationshiptype_set.all():
                        reltype.total = 0
                        reltype.save()

    def count(self, label=None):
        return self.gdb.get_nodes_count(label=label)

    def _get(self, node_id):
        return Node(node_id, self.graph)


class RelationshipSequence(BaseSequence):

    def create_list(self, eltos, with_labels=False):
        relationships = []
        if with_labels:
            for rel_id, rel_props, rel_label, source, target in eltos:
                relationship = Relationship(rel_id, self.graph,
                                            initial=rel_props,
                                            label=rel_label,
                                            source_dict=source,
                                            target_dict=target)
                relationships.append(relationship)
        else:
            for rel_id, rel_props in eltos:
                relationship = Relationship(rel_id, self.graph,
                                            initial=rel_props)
                relationships.append(relationship)
        return relationships


class RelationshipsManager(BaseManager):
    RelationshipDoesNotExist = RelationshipDoesNotExist

    def create(self, source, target, label, properties=None):
        if isinstance(source, Node):
            source_id = source.id
        else:
            source_id = source
        if isinstance(target, Node):
            target_id = target.id
        else:
            target_id = target
        if self.data.can_add_relationships():
            with transaction.atomic():
                if self.schema:
                    reltype = self.schema.relationshiptype_set.get(pk=label)
                    if not self.graph.relaxed:
                        properties = self._filter_dict(properties, reltype)
                    reltype.total += 1
                    reltype.save()
                self.data.total_relationships += 1
                self.data.last_modified_relationships = datetime.now()
                self.data.save()
            relationship_id = self.gdb.create_relationship(source_id, target_id,
                                                           label, properties)
            relationship = Relationship(relationship_id, self.graph,
                                        initial=properties)
            return relationship
        else:
            raise RelationshipsLimitReachedException

    def all(self):
        relationship_types = self.graph.schema.relationshiptype_set.all()
        relationship_labels = [
            str(relationship_type.id)
            for relationship_type in relationship_types]
        return RelationshipSequence(
            graph=self.graph,
            iterator_func=self.gdb.get_filtered_relationships,
            lookups=None,
            label=relationship_labels,
            include_properties=True)

    def filter(self, *lookups, **options):
        if "label" in options:
            label = options.get("label")
            if not lookups:
                eltos = RelationshipSequence(graph=self.graph, label=label,
                            iterator_func=self.gdb.get_relationships_by_label,
                            include_properties=True)
            else:
                eltos = RelationshipSequence(graph=self.graph, label=label,
                            lookups=lookups,
                            iterator_func=self.gdb.get_filtered_relationships,
                            include_properties=True)
        else:
            eltos = RelationshipSequence(graph=self.graph, label=label,
                            lookups=lookups,
                            iterator_func=self.gdb.get_filtered_relationships,
                            include_properties=True)
        return eltos

    def iterator(self):
        eltos = self.gdb.get_all_relationships(include_properties=True)
        for rel_id, rel_properties, rel_label, source, target in eltos:
            relationship = Relationship(rel_id, self.graph,
                                        initial=rel_properties,
                                        label=rel_label,
                                        source_dict=source,
                                        target_dict=target)
            yield relationship

    def in_bulk(self, id_list):
        relationships = []
        eltos = self.gdb.get_relationships(id_list, include_properties=True)
        for relationship_id, relationship_properties in eltos.items():
            relationship = Relationship(relationship_id, self.graph,
                                        initial=relationship_properties)
            relationships.append(relationship)
        return relationships

    def delete(self, **options):
        if "label" in options:
            label = options.get("label")
            eltos = self.gdb.get_relationships_by_label(
                label,
                include_properties=False
            )
            count = self.gdb.delete_relationships(
                [relationship_id for relationship_id, r_props, r_label in eltos]
            )
            with transaction.atomic():
                self.data.total_relationships -= count
                self.data.last_modified_relationships = datetime.now()
                self.data.save()
                if self.schema:
                    schema = self.schema
                    reltype = schema.relationshiptype_set.get(pk=label)
                    reltype.total = 0
                    reltype.save()
        elif "id" in options:
            relationship_ids = options.get("id")
            if not isinstance(relationship_ids, (list, tuple)):
                relationship_ids = [relationship_ids]
            for relationship_id in relationship_ids:
                Relationship(relationship_id, self.graph).delete()
        else:
            eltos = self.gdb.get_all_relationships(include_properties=False)
            self.gdb.delete_relationships(eltos)
            with transaction.atomic():
                self.data.total_relationships = 0
                self.data.last_modified_relationships = datetime.now()
                self.data.save()
                if self.schema:
                    schema = self.schema
                    for reltype in schema.relationshiptype_set.all():
                        reltype.total = 0
                        reltype.save()

    def count(self, label=None):
        return self.gdb.get_relationships_count(label=label)

    def _get(self, node_id):
        return Relationship(node_id, self.graph)


class NodeRelationshipsManager(BaseManager):

    def __init__(self, graph, node_id=None, node_label=None):
        super(NodeRelationshipsManager, self).__init__(graph)
        self.node_id = node_id
        self.node_label = node_label

    def create(self, target, label, properties=None, outgoing=False):
        if outgoing:
            source_id = self.node_id
            target_id = target.id
        else:
            source_id = target.id
            target_id = self.node_id
        if self.data.can_add_relationships():
            with transaction.atomic():
                if self.schema:
                    reltype = self.schema.relationshiptype_set.get(pk=label)
                    if not self.graph.relaxed:
                        properties = self._filter_dict(properties, reltype)
                    reltype.total += 1
                    reltype.save()
                self.data.total_relationships += 1
                self.data.save()
            relationship_id = self.gdb.create_relationship(source_id,
                                                           target_id,
                                                           label,
                                                           properties)
            relationship = Relationship(relationship_id, self.graph,
                                        initial=properties)
            return relationship
        else:
            raise RelationshipsLimitReachedException

    def all(self):
        relationship_types = self.graph.schema.relationshiptype_set.all()
        relationship_labels = [
            str(relationship_type.id)
            for relationship_type in relationship_types]
        relationships = []
        eltos = self.gdb.get_node_relationships(self.node_id,
                                                include_properties=True,
                                                label=relationship_labels)
        for relationship_id, relationship_properties in eltos:
            relationship = Relationship(relationship_id, self.graph,
                                        initial=relationship_properties)
            relationships.append(relationship)
        return relationships

    def filter(self, **options):
        label = None
        if "label" in options:
            label = options.get("label")
        relationships = []
        eltos = self.gdb.get_node_relationships(self.node_id,
                                                include_properties=True,
                                                label=label)
        for relationship_id, relationship_properties in eltos:
            relationship = Relationship(relationship_id, self.graph,
                                        initial=relationship_properties)
            relationships.append(relationship)
        return relationships

    def _create_relationship_list(self, eltos):
        relationships = []
        for relationship_id, relationship_properties in eltos:
            relationship = Relationship(relationship_id, self.graph,
                                        initial=relationship_properties)
            relationships.append(relationship)
        return relationships

    def incoming(self):
        relationships = []
        eltos = self.gdb.get_node_relationships(self.node_id, incoming=True,
                                                include_properties=True)
        for relationship_id, relationship_properties in eltos:
            relationship = Relationship(relationship_id, self.graph,
                                        initial=relationship_properties)
            relationships.append(relationship)
        return relationships

    def outgoing(self):
        relationships = []
        eltos = self.gdb.get_node_relationships(self.node_id, outgoing=True,
                                                include_properties=True)
        for relationship_id, relationship_properties in eltos:
            relationship = Relationship(relationship_id, self.graph,
                                        initial=relationship_properties)
            relationships.append(relationship)
        return relationships

    def iterator(self):
        iterator = self.gdb.get_node_relationships(include_properties=True)
        for relationship_id, relationship_properties in iterator.iteritems():
            relationship = Relationship(relationship_id, self.graph,
                                        initial=relationship_properties)
            yield relationship

    def in_bulk(self, id_list):
        relationships = []
        eltos = self.gdb.get_node_relationships(self.node_id, incoming=True,
                                                include_properties=True)
        for relationship_id, relationship_properties in eltos.items():
            relationship = Relationship(relationship_id, self.graph,
                                        initial=relationship_properties)
            relationships.append(relationship)
        return relationships

    def count(self, label=None):
        return self.gdb.get_nodes_relationships_count(label=label)

    def _get(self):
        return Relationship(self.node_id, self.graph)


class PropertyDict(dict):

    def __init__(self, element=None, *args, **kwargs):
        self.element = element
        super(PropertyDict, self).__init__(*args, **kwargs)

    def update(self, properties, **kwargs):
        super(PropertyDict, self).update(properties, **kwargs)
        if self.element:
            if isinstance(self.element, Node):
                self.element.gdb.update_node_properties(self.element.id,
                                                        properties=properties)
            elif isinstance(self.element, Relationship):
                self.element.gdb.update_relationship_properties(self.element.id,
                                                        properties=properties)


class BaseElement(object):
    """
    Base element class for building Node and Relationship classes.
    """

    def __init__(self, id, graph, properties=None, initial=None, label=None,
                 source_dict=None, target_dict=None):
        self._id = int(id)
        self.graph = graph
        self.gdb = graph.gdb
        # self.schema = (not graph.relaxed) and graph.schema
        self.schema = graph.schema
        self.data = graph.data
        self._label = label
        self._inital = initial
        if isinstance(initial, dict):
            self._properties = initial
        elif not properties:
            self._properties = None
            self._get_properties()
        else:
            self._properties = self._set_properties(properties)
        self._properties_to_display = None
        # Just for relationships
        self._source = None
        self._display = None
        if source_dict:
            self._source_dict = source_dict
            self._source = Node(source_dict["id"], graph,
                                initial=source_dict["properties"],
                                label=source_dict["label"])
        self._target = None
        if target_dict:
            self._target_dict = target_dict
            self._target = Node(target_dict["id"], graph,
                                initial=target_dict["properties"],
                                label=target_dict["label"])

    def get(self, key, *args, **kwargs):
        try:
            return self.__getitem__(key)
        except KeyError:
            if args:
                return args[0]
            elif "default" in kwargs:
                return kwargs["default"]
            else:
                raise KeyError(key)

    def __contains__(self, obj):
        return obj in self._properties

    def set(self, key, value):
        self.__setitem__(key, value)

    def __len__(self):
        return len(self._properties)

    def __iter__(self):
        return self._properties.__iter__()

    def __eq__(self, obj):
        return (hasattr(obj, "id")
                and self.id == obj.id
                and hasattr(obj, "__class__")
                and self.__class__ == obj.__class__)

    def __ne__(self, obj):
        return not self.__cmp__(obj)

    def __nonzero__(self):
        return bool(self.id and self.gdb
                    and isinstance(self._properties, dict))

    def __repr__(self):
        return self.__unicode__()

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return u"<%s: %s>" % (self.__class__.__name__, self.id)

    def _get_id(self):
        return self._id
    id = property(_get_id)

    def _filter_dict(self, properties):
        if properties:
            if self.schema:
                property_keys = self._get_property_keys()
                popped = [properties.pop(k) for k in properties.keys()
                                            if (k not in property_keys
                                                or unicode(k).startswith("_"))]
                del popped
                return properties
            else:
                return dict(filter(lambda (k, v):
                                        not unicode(k).startswith("_"),
                                        properties.iteritems()))
        else:
            return {}

    def _get_display(self, separator=u", "):
        if not self._display:
            if not self._properties:
                self._display = u"%s" % self._id
            else:
                properties_to_display = self._get_properties_display()
                if not properties_to_display:
                    properties_to_display = []
                    properties_values = self._properties.values()[:5]
                    for i in range(len(properties_values)):
                        if properties_values[i]:
                            try:
                                unicode_value = unicode(properties_values[i])

                                value_strip = unicode_value.strip()
                                if len(value_strip) > 0:
                                    properties_to_display.append(value_strip)
                            except UnicodeDecodeError:
                                pass
                if properties_to_display:
                    self._display = separator.join(properties_to_display)
                else:
                    self._display = u"%s" % self._id
        return self._display
    display = property(_get_display)


class Node(BaseElement):
    """
    Node class.
    """

    def delete(self, key=None):
        if key:
            self.__delitem__(key)
        else:
            label = self.label
            with transaction.atomic():
                self.data.total_nodes -= 1
                self.data.last_modified_nodes = datetime.now()
                self.data.save()
                if self.schema:
                    nodetype = self.schema.nodetype_set.get(pk=label)
                    nodetype.total -= 1
                    nodetype.save()
                try:
                    self.gdb.delete_node(self.id)
                except:
                    transaction.rollback()
            del self

    def get_type(self):
        return NodeType.objects.get(id=self.label)

    def _label_display(self):
        if self.schema:
            return self.schema.get_node_name(self.label)
        else:
            return self.label

    def to_json(self):
        return {
            'id': str(self.id),
            'nodetype': self.label_display,
            'properties': self.properties.copy(),
            'nodetypeId': self.get_type().id,
            'label': self.display + ' (' + str(self.id) + ')',
            'color': self.get_type().get_color(),
            'x': random.uniform(0, 1),
            'y': random.uniform(0, 1),
            'size': 1
        }

    def __getitem__(self, key):
        # Not need anymore because _properties is always updated
        # if key not in self._properties:
        #     self._properties[key] = self.gdb.get_node_property(self.id, key)
        return self._properties[key]

    def __setitem__(self, key, value):
        self.gdb.set_node_property(self.id, key, value)
        self._properties[key] = value

    def __delitem__(self, key):
        self.gdb.delete_node_property(self.id, key)
        del self._properties[key]

    def _get_label(self):
        if not self._label:
            self._label = self.gdb.get_node_label(self.id)
        return self._label
    label = property(_get_label)

    def _relationships(self):
        return NodeRelationshipsManager(self.graph, self.id)
    relationships = property(_relationships)

    def _get_properties_display(self):
        if not self._properties_to_display:
            displays = []
            if self.schema:
                displays = self.schema.get_displays(self.label)
            # TODO: Get displays when there is not a schema
            properties_to_display = []
            properties = self._properties
            for display in displays:
                if display.key in properties:
                    if display.datatype == u"b":  # Boolean
                        if properties[display.key]:
                            properties_to_display.append(display.key)
                        else:
                            properties_to_display.append(u"¬%s" % display.key)
                    else:
                        try:
                            unicode_value = unicode(properties[display.key])
                            value_strip = unicode_value.strip()
                            if len(value_strip) > 0:
                                properties_to_display.append(value_strip)
                        except UnicodeDecodeError:
                            pass
            self._properties_to_display = properties_to_display
        return self._properties_to_display

    def _get_property_keys(self):
        itemtypes = self.schema.nodetype_set.filter(pk=self.label)
        if itemtypes:
            property_keys = [p.key for p in itemtypes[0].properties.all()]
        else:
            property_keys = []
        return property_keys

    def _get_properties(self):
        if self._inital is None and self._properties is None:
            self._properties = self.gdb.get_node_properties(self.id)
        return self._properties

    def _set_properties(self, properties=None):
        if not properties:
            return None
        properties = self._filter_dict(properties)
        self.gdb.set_node_properties(self.id, properties=properties)
        self._properties = PropertyDict(self, properties)
        return self._properties

    def _del_properties(self):
        self.gdb.delete_node_properties()
        self._properties = {}

    properties = property(_get_properties, _set_properties, _del_properties)
    label_display = property(_label_display)


class Relationship(BaseElement):
    """
    Relationship class.
    """

    def delete(self, key=None):
        if key:
            self.__delitem__(key)
        else:
            with transaction.atomic():
                self.data.total_relationships -= 1
                self.data.save()
                if self.schema:
                    schema = self.schema
                    reltype = schema.relationshiptype_set.get(pk=self.label)
                    reltype.total -= 1
                    reltype.save()
                try:
                    self.gdb.delete_relationship(self.id)
                except:
                    transaction.rollback()
            del self

    def get_type(self):
        return RelationshipType.objects.get(id=self.label)

    def _label_display(self):
        if self.schema:
            return self.schema.get_relationship_name(self.label)
        else:
            return self.label

    def to_json(self):
        return {
            'id': str(self.id),
            'source': str(self.source.id),
            'target': str(self.target.id),
            'reltypeId': self.get_type().id,
            'reltype': self.label_display,
            'fullReltype': self.get_type().__unicode__(),
            'color': self.get_type().get_color(),
            'properties': self.properties
        }

    def __getitem__(self, key):
        # Not needed anymore since _properties is always updated
        # if key not in self._properties:
        #     value = self.gdb.get_relationship_property(self.id, key)
        #     self._properties[key] = value
        return self._properties[key]

    def __setitem__(self, key, value):
        self.gdb.set_relationship_property(self.id, key, value)
        self._properties[key] = value

    def __delitem__(self, key):
        self.gdb.delete_relationship_property(self.id, key)
        del self._properties[key]

    def _get_source(self):
        if not self._source:
            node_id, properties = self.gdb.get_relationship_source(self.id)
            self._source = Node(node_id, self.graph, initial=properties)
        return self._source

    def _set_source(self, node):
        self.gdb.set_relationship_source(self.id, node.id)

    source = property(_get_source, _set_source)

    def _get_target(self):
        if not self._target:
            node_id, properties = self.gdb.get_relationship_target(self.id)
            self._target = Node(node_id, self.graph, initial=properties)
        return self._target

    def _set_target(self, node):
        self.gdb.set_relationship_target(self.id, node.id)

    target = property(_get_target, _set_target)

    def _get_label(self):
        if not self._label:
            self._label = self.gdb.get_relationship_label(self.id)
        return self._label
    label = property(_get_label)

    def _get_property_keys(self):
        itemtypes = self.schema.relationshiptype_set.filter(pk=self.label)
        if itemtypes:
            property_keys = [p.key for p in itemtypes[0].properties.all()]
        else:
            property_keys = []
        return property_keys

    def _get_properties(self):
        if self._inital is None and self._properties is None:
            self._properties = self.gdb.get_relationship_properties(self.id)
        return self._properties

    def _set_properties(self, properties=None):
        if not properties:
            return None
        properties = self._filter_dict(properties)
        self.gdb.set_relationship_properties(self.id,
                                             properties=properties)
        self._properties = PropertyDict(self, properties)
        return self._properties

    def _del_properties(self):
        self.gdb.delete_relationship_properties()
        self._properties = {}

    properties = property(_get_properties, _set_properties, _del_properties)
    label_display = property(_label_display)
