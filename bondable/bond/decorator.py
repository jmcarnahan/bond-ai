import inspect
from typing import Any, Callable, Optional, Dict, get_origin, get_args
import logging
import threading
from functools import wraps

LOGGER = logging.getLogger(__name__)

PYTHON_TO_JSON_SCHEMA = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    type(None): "null"
}

def get_json_schema_type(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty:
        return "string"  # should be any but json schema doesn't have any
    origin = get_origin(annotation)  
    if origin is list:
        return "array"
    elif origin is dict:
        return "object"
    return PYTHON_TO_JSON_SCHEMA.get(annotation, "any") 

def get_tool_info(func: Callable, 
                  description: Optional[str] = None, 
                  arg_descriptions: Optional[Dict[str, str]] = None) -> str:

    signature = inspect.signature(func)
    try:
        source_code = inspect.getsource(func)
    except OSError:
        source_code = "Source code not available"

    docstring = inspect.getdoc(func)

    # LOGGER.info(f"Function Name: {func_name}")
    # LOGGER.info(f"Signature: {signature}")
    # LOGGER.info(f"Docstring: {docstring}")
    # LOGGER.info(f"Source Code:\n{source_code}")

    schema = {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": description or "",
            "strict": False,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
    
    for name, param in signature.parameters.items():
        if name == "self":
            continue
        schema["function"]["parameters"]["properties"][name] = {
            "type": get_json_schema_type(param.annotation),
            "description": arg_descriptions.get(name, "") if arg_descriptions else ""  
        }
        if param.default is param.empty:
            schema["function"]["parameters"]["required"].append(name)
        
    # return {'name': func.__name__, 'schema':schema, 'source_code': source_code, 'signature': signature, 'docstring': docstring if docstring else ""}
    return {'name': func.__name__, 'schema':schema, 'source_code': source_code, 'docstring': docstring if docstring else ""}

def bondtool(description: Optional[str] = None, arg_descriptions: Optional[Dict[str, str]] = None):
    # TODO: should get the descriptions if they are not provided using llm
    LOGGER.debug(f"Creating bondtool with description: {description} and arg_descriptions: {arg_descriptions}")
    def decorator(func: Callable) -> Callable:
        func.__bondtool__ = get_tool_info(func, description, arg_descriptions)
        LOGGER.debug(f"Created tool info: {func.__bondtool__}")
        return func
    return decorator
