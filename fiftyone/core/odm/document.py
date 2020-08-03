"""
Base classes for documents that back dataset contents.

| Copyright 2017-2020, Voxel51, Inc.
| `voxel51.com <https://voxel51.com/>`_
|
"""
# pragma pylint: disable=redefined-builtin
# pragma pylint: disable=unused-wildcard-import
# pragma pylint: disable=wildcard-import
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from builtins import *

# pragma pylint: enable=redefined-builtin
# pragma pylint: enable=unused-wildcard-import
# pragma pylint: enable=wildcard-import

from copy import deepcopy
import json
import re

from bson import json_util
from bson.objectid import ObjectId
import mongoengine
import pymongo

import fiftyone.core.utils as fou

import eta.core.serial as etas


class SerializableDocument(object):
    """Mixin for documents that can be serialized in BSON or JSON format."""

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return self.fancy_repr()

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        return self.to_dict() == other.to_dict()

    def __copy__(self):
        return self.copy()

    def fancy_repr(
        self, class_name=None, select_fields=None, exclude_fields=None
    ):
        """Generates a customizable string representation of the document.

        Args:
            class_name (None): optional class name to use
            select_fields (None): iterable of field names to restrict to
            exclude_fields (None): iterable of field names to exclude

        Returns:
            a string representation of the document
        """
        d = {}
        for f in self._get_repr_fields():
            if f.startswith("_") or (
                f != "id"
                and (
                    (select_fields is not None and f not in select_fields)
                    or (exclude_fields is not None and f in exclude_fields)
                )
            ):
                continue

            value = getattr(self, f)

            if isinstance(value, ObjectId):
                d[f] = str(value)
            else:
                d[f] = value

        doc_name = class_name or self.__class__.__name__
        doc_str = fou.pformat(d)
        return "<%s: %s>" % (doc_name, doc_str)

    def _get_repr_fields(self):
        """Returns an ordered tuple of field names that should be included in
        the ``repr`` of the document.

        Returns:
            a tuple of field names
        """
        raise NotImplementedError("Subclass must implement `_get_repr_fields`")

    def copy(self):
        """Returns a deep copy of the document.

        Returns:
            a document
        """
        return deepcopy(self)

    def to_dict(self, extended=False):
        """Serializes this document to a BSON/JSON dictionary.

        Args:
            extended (False): whether to serialize extended JSON constructs
                such as ObjectIDs, Binary, etc. into JSON format

        Returns:
            a dict
        """
        raise NotImplementedError("Subclass must implement `to_dict()`")

    @classmethod
    def from_dict(cls, d, extended=False):
        """Loads the document from a BSON/JSON dictionary.

        Args:
            d: a dictionary
            extended (False): whether the input dictionary may contain
                serialized extended JSON constructs

        Returns:
            the document
        """
        raise NotImplementedError("Subclass must implement `from_dict()`")

    def to_json(self, pretty_print=False):
        """Serializes the document to a JSON string.

        Args:
            pretty_print (False): whether to render the JSON in human readable
                format with newlines and indentations

        Returns:
            a JSON string
        """
        d = self.to_dict(extended=True)
        return etas.json_to_str(d, pretty_print=pretty_print)

    @classmethod
    def from_json(cls, s):
        """Loads the document from a JSON string.

        Returns:
            the document
        """
        d = json_util.loads(s)
        return cls.from_dict(d, extended=False)


class MongoEngineBaseDocument(SerializableDocument):
    """Mixin for all ``mongoengine.base.BaseDocument`` subclasses that
    implements the :class:`SerializableDocument` interface.
    """

    def _get_repr_fields(self):
        # pylint: disable=no-member
        return self._fields_ordered

    def to_dict(self, extended=False):
        if extended:
            return json.loads(self._to_json())

        return json_util.loads(self._to_json())

    @classmethod
    def from_dict(cls, d, extended=False):
        if not extended:
            try:
                # Attempt to load the document directly, assuming it is in
                # extended form

                # pylint: disable=no-member
                return cls._from_son(d)
            except Exception:
                pass

        # pylint: disable=no-member
        bson_data = json_util.loads(json_util.dumps(d))
        return cls._from_son(bson_data)

    def _to_json(self):
        # @todo(Tyler) mongoengine snippet, to be replaced
        # pylint: disable=no-member
        return json_util.dumps(self.to_mongo(use_db_field=True))


class BaseDocument(MongoEngineBaseDocument):
    """Base class for documents that are written to the database in their own
    collections.

    The ID of a document is automatically populated when it is added to the
    database, and the ID of a document is ``None`` if it has not been added to
    the database.

    Attributes:
        id: the ID of the document, or ``None`` if it has not been added to the
            database
    """

    def __eq__(self, other):
        # pylint: disable=no-member
        if self.id != other.id:
            return False

        return super().__eq__(other)

    def _get_repr_fields(self):
        # pylint: disable=no-member
        return ("id",) + tuple(f for f in self._fields_ordered if f != "id")

    @property
    def ingest_time(self):
        """The time the document was added to the database, or ``None`` if it
        has not been added to the database.
        """
        # pylint: disable=no-member
        return self.id.generation_time if self.in_db else None

    @property
    def in_db(self):
        """Whether the underlying :class:`fiftyone.core.odm.Document` has
        been inserted into the database.
        """
        return self.id is not None

    def copy(self):
        """Returns a copy of the document that does not have its `id` set.

        Returns:
            a :class:`Document`
        """
        doc = deepcopy(self)
        if doc.id is not None:
            # pylint: disable=attribute-defined-outside-init
            doc.id = None

        return doc


class BaseEmbeddedDocument(MongoEngineBaseDocument):
    """Base class for documents that are embedded within other documents and
    therefore are not stored in their own collection in the database.
    """

    pass


class Document(BaseDocument, mongoengine.Document):
    """Base class for documents that are stored in a MongoDB collection.

    The ID of a document is automatically populated when it is added to the
    database, and the ID of a document is ``None`` if it has not been added to
    the database.

    Attributes:
        id: the ID of the document, or ``None`` if it has not been added to the
            database
    """

    meta = {"abstract": True}

    def save(self, validate=True, clean=True, **kwargs):
        """Save the :class:`Document` to the database.

        If the document already exists, it will be updated, otherwise it will
        be created.

        Args:
            validate (True): validates the document
            clean (True): call the document's clean method; requires
                ``validate`` to be True

        Returns:
            self
        """
        # pylint: disable=no-member
        if self._meta.get("abstract"):
            raise mongoengine.InvalidDocumentError(
                "Cannot save an abstract document."
            )

        if validate:
            self.validate(clean=clean)

        doc_id = self.to_mongo(fields=[self._meta["id_field"]])
        created = "_id" not in doc_id or self._created

        # It might be refreshed by the pre_save_post_validation hook, e.g., for
        # etag generation
        doc = self.to_mongo()

        if self._meta.get("auto_create_index", True):
            self.ensure_indexes()

        try:
            # Save a new document or update an existing one
            if created:
                # Save new document

                # insert_one will provoke UniqueError alongside save does not
                # therefore, it need to catch and call replace_one.
                collection = self._get_collection()

                object_id = None

                if "_id" in doc:
                    raw_object = collection.find_one_and_replace(
                        {"_id": doc["_id"]}, doc
                    )
                    if raw_object:
                        object_id = doc["_id"]

                if not object_id:
                    object_id = collection.insert_one(doc).inserted_id
            else:
                # Update existing document
                object_id = doc["_id"]
                created = False

                updates, removals = self._delta()

                update_doc = {}
                if updates:
                    update_doc["$set"] = updates
                if removals:
                    update_doc["$unset"] = removals

                if update_doc:
                    updated_existing = self._update(
                        object_id, update_doc, **kwargs
                    )

                    if updated_existing is False:
                        created = True
                        # !!! This is bad, means we accidentally created a
                        # new, potentially corrupted document. See
                        # https://github.com/MongoEngine/mongoengine/issues/564

        except pymongo.errors.DuplicateKeyError as err:
            message = "Tried to save duplicate unique keys (%s)"
            raise mongoengine.NotUniqueError(message % err)
        except pymongo.errors.OperationFailure as err:
            message = "Could not save document (%s)"
            if re.match("^E1100[01] duplicate key", str(err)):
                # E11000 - duplicate key error index
                # E11001 - duplicate key on update
                message = "Tried to save duplicate unique keys (%s)"
                raise mongoengine.NotUniqueError(message % err)
            raise mongoengine.OperationError(message % err)

        # Make sure we store the PK on this document now that it's saved
        id_field = self._meta["id_field"]
        if created or id_field not in self._meta.get("shard_key", []):
            self[id_field] = self._fields[id_field].to_python(object_id)

        self._clear_changed_fields()
        self._created = False

        return self

    def _update(self, object_id, update_doc, **kwargs):
        """Updates an existing document.

        Helper method; should only be used by :meth:`Document.save`.
        """
        result = (
            self._get_collection()
            .update_one({"_id": object_id}, update_doc, upsert=True)
            .raw_result
        )

        if result is not None:
            updated_existing = result.get("updatedExisting")
        else:
            updated_existing = None

        return updated_existing


class DynamicDocument(BaseDocument, mongoengine.DynamicDocument):
    """Base class for dynamic documents that are stored in a MongoDB
    collection.

    Dynamic documents can have arbitrary fields added to them.

    The ID of a document is automatically populated when it is added to the
    database, and the ID of a document is ``None`` if it has not been added to
    the database.

    Attributes:
        id: the ID of the document, or ``None`` if it has not been added to the
            database
    """

    meta = {"abstract": True}


class EmbeddedDocument(BaseEmbeddedDocument, mongoengine.EmbeddedDocument):
    """Base class for documents that are embedded within other documents and
    therefore are not stored in their own collection in the database.
    """

    meta = {"abstract": True}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validate()


class DynamicEmbeddedDocument(
    BaseEmbeddedDocument, mongoengine.DynamicEmbeddedDocument,
):
    """Base class for dynamic documents that are embedded within other
    documents and therefore aren't stored in their own collection in the
    database.

    Dynamic documents can have arbitrary fields added to them.
    """

    meta = {"abstract": True}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validate()
