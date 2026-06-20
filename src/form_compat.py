"""Small multipart form parser used when stdlib cgi is unavailable.

Python 3.13 removed the deprecated cgi module. TexCat only needs the
FieldStorage pieces used by browser FormData: getfirst(), membership lookup,
and uploaded file fields with filename/file attributes.
"""

from __future__ import annotations

from email import policy
from email.parser import BytesParser
from io import BytesIO
from typing import Any


class FormField:
    def __init__(self, name: str, value: str = "", filename: str | None = None, data: bytes | None = None) -> None:
        self.name = name
        self.value = value
        self.filename = filename
        self.file = BytesIO(data or b"")


class FieldStorage:
    def __init__(self, fp: Any, headers: Any, environ: dict[str, str]) -> None:
        content_type = environ.get("CONTENT_TYPE", "") or headers.get("Content-Type", "")
        try:
            content_length = int(environ.get("CONTENT_LENGTH", "0") or "0")
        except ValueError:
            content_length = 0
        body = fp.read(content_length)
        self._fields: dict[str, FormField | list[FormField]] = {}
        self._parse_multipart(content_type, body)

    def __contains__(self, name: str) -> bool:
        return name in self._fields

    def __getitem__(self, name: str) -> FormField | list[FormField]:
        return self._fields[name]

    def getfirst(self, name: str, default: str = "") -> str:
        if name not in self._fields:
            return default
        field = self._fields[name]
        if isinstance(field, list):
            if not field:
                return default
            field = field[0]
        return field.value

    def _add_field(self, field: FormField) -> None:
        existing = self._fields.get(field.name)
        if existing is None:
            self._fields[field.name] = field
        elif isinstance(existing, list):
            existing.append(field)
        else:
            self._fields[field.name] = [existing, field]

    def _parse_multipart(self, content_type: str, body: bytes) -> None:
        if not content_type.lower().startswith("multipart/form-data"):
            return
        message_bytes = (
            f"Content-Type: {content_type}\r\n"
            "MIME-Version: 1.0\r\n\r\n"
        ).encode("utf-8") + body
        message = BytesParser(policy=policy.default).parsebytes(message_bytes)
        if not message.is_multipart():
            return
        for part in message.iter_parts():
            if part.get_content_disposition() != "form-data":
                continue
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename:
                self._add_field(FormField(str(name), filename=filename, data=payload))
            else:
                charset = part.get_content_charset() or "utf-8"
                value = payload.decode(charset, errors="replace")
                self._add_field(FormField(str(name), value=value))
