# -*- coding: utf-8 -*-
from django.shortcuts import get_object_or_404
from graphs.models import Graph
from schemas.serializers import (NodeTypesSerializer,
                                 RelationshipTypesSerializer,
                                 NodeTypeSerializer,
                                 RelationshipTypeSerializer)
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class NodeTypesView(APIView):

    def get(self, request, graph_slug, format=None):
        """
        Returns all the nodetypes of a graph
        """
        graph = get_object_or_404(Graph, slug=graph_slug)
        nodetypes = graph.schema.nodetype_set.all()

        serializer = NodeTypesSerializer(nodetypes, many=True)

        return Response(serializer.data)

    def post(self, request, graph_slug, format=None):
        """
        Create a new node type
        """
        graph = get_object_or_404(Graph, slug=graph_slug)
        # We get the data from the request
        post_data = request.data
        # We get the schema id
        post_data['schema'] = graph.schema_id

        serializer = NodeTypesSerializer(data=post_data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RelationshipTypesView(APIView):

    def get(self, request, graph_slug, format=None):
        """
        Returns all the relationship types of a graph
        """
        graph = get_object_or_404(Graph, slug=graph_slug)
        relationshiptypes = graph.schema.relationshiptype_set.all()

        serializer = RelationshipTypesSerializer(relationshiptypes, many=True)

        return Response(serializer.data)

    def post(self, request, graph_slug, format=None):
        """
        Create a new node type
        """
        graph = get_object_or_404(Graph, slug=graph_slug)
        # We get the data from the request
        post_data = request.data
        # We get the schema id
        post_data['schema'] = graph.schema_id

        serializer = RelationshipTypesSerializer(data=post_data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class NodeTypeView(APIView):

    def get(self, request, graph_slug, type_slug, format=None):
        """
        Returns info related to the node type
        """
        graph = get_object_or_404(Graph, slug=graph_slug)
        nodetype = (
            graph.schema.nodetype_set.all().filter(slug=type_slug)[0])

        serializer = NodeTypeSerializer(nodetype)

        return Response(serializer.data)

    def delete(self, request, graph_slug, type_slug, format=None):
        """
        Delete the node type from the schema
        """
        graph = get_object_or_404(Graph, slug=graph_slug)
        nodetype = (
            graph.schema.nodetype_set.all().filter(slug=type_slug)[0])

        # We get the parameter to check what to remove
        remove_nodes = request.data.get('remove_nodes', None)
        if remove_nodes:
            # We need to remove all the related nodes and
            # relationships
            graph.nodes.delete(label=nodetype.id)

        serializer = NodeTypeSerializer(nodetype)
        serializer.instance.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class RelationshipTypeView(APIView):

    def get(self, request, graph_slug, type_slug, format=None):
        """
        Returns info related to the relationship type
        """
        graph = get_object_or_404(Graph, slug=graph_slug)
        relationshiptype = (
            graph.schema.relationshiptype_set.all().filter(slug=type_slug)[0])

        serializer = RelationshipTypeSerializer(relationshiptype)

        return Response(serializer.data)

    def delete(self, request, graph_slug, format=None):
        """
        Delete the relationship type from the schema
        """
        pass
