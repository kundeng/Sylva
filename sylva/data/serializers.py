from schemas.models import NodeType, RelationshipType
from rest_framework import serializers


class GetNodesSerializer(serializers.ModelSerializer):
    total = serializers.SerializerMethodField('count_func')
    nodes = serializers.SerializerMethodField('nodes_func')

    def count_func(self, nodetype):
        # We get the nodes of the graph
        # We need to filter by this nodetype
        filtered_nodes = (
            nodetype.schema.graph.nodes.filter(label=nodetype.id))

        # We are ready to return the result
        return len([node for node in filtered_nodes])

    def nodes_func(self, nodetype):
        # We get the nodes of the graph
        # We need to filter by this nodetype
        filtered_nodes = (
            nodetype.schema.graph.nodes.filter(label=nodetype.id))

        nodes = list()

        for node in filtered_nodes:
            nodes.append(node.properties)

        # We are ready to return the result
        return nodes

    class Meta:
        model = NodeType
        fields = ('total', 'nodes')


class GetRelationshipsSerializer(serializers.ModelSerializer):
    total = serializers.SerializerMethodField('count_func')
    relationships = serializers.SerializerMethodField('rels_func')

    def count_func(self, relationshiptype):
        # We get the relationships of the graph
        # We need to filter by this relationshiptype
        filtered_relationships = (
            relationshiptype.schema.graph.relationships.filter(
                label=relationshiptype.id))

        # We are ready to return the result
        return len([rel for rel in filtered_relationships])

    def rels_func(self, relationshiptype):
        # We get the relationships of the graph
        # We need to filter by this relationshiptype
        filtered_relationships = (
            relationshiptype.schema.graph.relationships.filter(
                label=relationshiptype.id))

        relationships = list()

        for relationship in filtered_relationships:
            relationship_dict = dict()
            relationship_dict['source'] = (
                relationship.source.properties)
            relationship_dict['target'] = (
                relationship.target.properties)
            relationship_dict['properties'] = (
                relationship.properties)
            relationships.append(relationship_dict)

        # We are ready to return the result
        return relationships

    class Meta:
        model = RelationshipType
        fields = ('total', 'relationships')
