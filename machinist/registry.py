from __future__ import annotations

import hashlib
import json
import importlib.util
import math
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List, Set, Callable
import uuid


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_payload(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
    return h.hexdigest()


@dataclass
class ToolSpec:
    name: str
    signature: str
    docstring: str
    inputs: Dict[str, str]
    outputs: Dict[str, str]
    failure_modes: str
    deterministic: bool
    imports: List[str] = field(default_factory=list)
    semantic_tags: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, indent=2)


@dataclass
class ToolMetadata:
    tool_id: str
    version: str
    created_at: str
    spec: ToolSpec
    source_path: Path
    tests_path: Path
    test_results_path: Path
    dependencies: Dict[str, str]
    security_policy: str
    capability_profile: str
    model: str
    template_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["spec"] = asdict(self.spec)
        payload["source_path"] = str(self.source_path)
        payload["tests_path"] = str(self.tests_path)
        payload["test_results_path"] = str(self.test_results_path)
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=True, sort_keys=True, indent=2)


class ToolRegistry:


    """


    Simple filesystem-backed registry. Each tool gets its own directory:


    registry/<tool_id>/metadata.json


    """





    def __init__(self, root: Path) -> None:


        self.root = root


        self.root.mkdir(parents=True, exist_ok=True)


        self._executable_cache: Dict[str, Callable] = {}


        self._cached_specs_dir().mkdir(parents=True, exist_ok=True) # Ensure cache dir exists





    def _entry_dir(self, tool_id: str) -> Path:


        return self.root / tool_id





    def _cached_specs_dir(self) -> Path:


        return self.root / "cached_specs"





    def cache_spec(self, spec: ToolSpec | Any, context: Dict[str, Any]) -> str:


        """


        Caches a generated ToolSpec or CompositionSpec along with its context.


        Returns a unique cache_id.


        """


        cache_id = str(uuid.uuid4())


        cache_entry_path = self._cached_specs_dir() / f"{cache_id}.json"


        


        if isinstance(spec, ToolSpec):


            spec_data = asdict(spec)


            spec_type = "ToolSpec"


        elif hasattr(spec, 'pipeline_id'): # Duck-typing for CompositionSpec


            spec_data = asdict(spec)


            spec_type = "CompositionSpec"


        else:


            raise TypeError(f"Unsupported spec type for caching: {type(spec)}")





        payload = {


            "cache_id": cache_id,


            "timestamp": _now_iso(),


            "spec_type": spec_type,


            "spec": spec_data,


            "context": context,


        }


        cache_entry_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


        return cache_id





    def load_cached_spec(self, cache_id: str) -> Optional[Tuple[ToolSpec | Any, Dict[str, Any]]]:


        """


        Loads a cached spec and its context by cache_id.


        Returns (spec_object, context) or None if not found.


        """


        cache_entry_path = self._cached_specs_dir() / f"{cache_id}.json"


        if not cache_entry_path.exists():


            return None


        


        try:


            payload = json.loads(cache_entry_path.read_text(encoding="utf-8"))


            spec_type = payload["spec_type"]


            spec_data = payload["spec"]


            context = payload["context"]





            if spec_type == "ToolSpec":


                spec_obj = ToolSpec(**spec_data)


            elif spec_type == "CompositionSpec":


                from .templates import CompositionSpec, CompositionStep, StepBinding, FailurePolicy


                steps = [CompositionStep(
                    id=s['id'],
                    tool_id=s['tool_id'],
                    bind={k: StepBinding(**v) if isinstance(v, dict) else StepBinding(v) for k, v in s.get('bind', {}).items()},
                    foreach=s.get('foreach'),
                    outputs=s.get('outputs', {}),
                    if_condition=s.get('if_condition'),
                    then_tool_id=s.get('then_tool_id'),
                    then_bind={k: StepBinding(**v) if isinstance(v, dict) else StepBinding(v) for k, v in s.get('then_bind', {}).items()}
                ) for s in spec_data['steps']]


                policies = [FailurePolicy(**p) for p in spec_data.get('failure_policy', [])]


                spec_obj = CompositionSpec(


                    pipeline_id=spec_data['pipeline_id'],


                    description=spec_data['description'],


                    inputs=spec_data.get('inputs', {}),


                    steps=steps,


                    global_postconditions=spec_data.get('global_postconditions', []),


                    failure_policy=policies,


                    semantic_tags=spec_data.get('semantic_tags', [])


                )


            else:


                raise TypeError(f"Unknown spec type '{spec_type}' found in cache for ID {cache_id}")





            return spec_obj, context


        except Exception as e:


            print(f"Error loading cached spec {cache_id}: {e}")


            return None


    def find_workflow_by_id(self, pipeline_id: str) -> Optional[Any]: # Returns CompositionSpec
        """Finds a cached CompositionSpec by its pipeline_id."""
        for file in self._cached_specs_dir().glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                if data.get("spec_type") == "CompositionSpec":
                    spec_data = data["spec"]
                    if spec_data.get("pipeline_id") == pipeline_id:
                        # Rehydrate
                        # Avoid circular import by doing minimal dict return or lazy import
                        # For now, return the dict, let caller hydrate? 
                        # Or duplicate hydration logic.
                        # Let's call load_cached_spec
                        obj, _ = self.load_cached_spec(file.stem)
                        return obj
            except:
                continue
        return None

    def get_executable(self, tool_id: str) -> Optional[Callable]:


        """


        Dynamically loads and returns the executable function for a given tool_id.


        Results are cached in memory.


        """


        if tool_id in self._executable_cache:


            return self._executable_cache[tool_id]





        metadata = self.load(tool_id)


        if not metadata:


            return None





        source_path = Path.cwd() / metadata.source_path


        module_name = source_path.stem


        func_name = metadata.spec.name





        if not source_path.exists():


            raise FileNotFoundError(f"Source file for tool {tool_id} not found at {source_path}")





        try:


            spec = importlib.util.spec_from_file_location(module_name, source_path)


            if not spec or not spec.loader:


                raise ImportError(f"Could not create module spec for {module_name}")


            


            module = importlib.util.module_from_spec(spec)


            sys.modules[module_name] = module


            spec.loader.exec_module(module)


            


            func = getattr(module, func_name, None)


            if not func or not callable(func):


                raise AttributeError(f"Function '{func_name}' not found or not callable in {module_name}")





            self._executable_cache[tool_id] = func


            return func





        except Exception as e:


            print(f"Error loading executable for tool {tool_id}: {e}")


            return None





    def register(self, metadata: ToolMetadata) -> Path:


        entry_dir = self._entry_dir(metadata.tool_id)


        entry_dir.mkdir(parents=True, exist_ok=True)


        meta_path = entry_dir / "metadata.json"


        meta_path.write_text(metadata.to_json(), encoding="utf-8")


        return meta_path





    def resolve_id(self, spec: ToolSpec, source_code: str) -> str:


        return _hash_payload(spec.to_json(), source_code)





    def load(self, tool_id: str) -> Optional[ToolMetadata]:


        path = self._entry_dir(tool_id) / "metadata.json"


        if not path.exists():


            return None


        data = json.loads(path.read_text(encoding="utf-8"))


        


        spec_data = data["spec"]


        spec_data.setdefault("imports", [])


        


        spec = ToolSpec(**spec_data)


        return ToolMetadata(


            tool_id=data["tool_id"],


            version=data["version"],


            created_at=data["created_at"],


            spec=spec,


            source_path=Path(data["source_path"]),


            tests_path=Path(data["tests_path"]),


            test_results_path=Path(data["test_results_path"]),


            dependencies=data.get("dependencies", {}),


            security_policy=data.get("security_policy", ""),


            capability_profile=data.get("capability_profile", ""),


            model=data.get("model", ""),


            template_id=data.get("template_id"),


        )





    def find_by_template_id(self, template_id: str) -> List[str]:


        """Finds all tool_ids that were generated from a given template_id."""


        matching_tool_ids = []


        if not self.root.exists():


            return matching_tool_ids


            


        for tool_id_dir in self.root.iterdir():


            if tool_id_dir.is_dir():


                metadata = self.load(tool_id_dir.name)


                if metadata and metadata.template_id == template_id:


                    matching_tool_ids.append(metadata.tool_id)


        return matching_tool_ids


    def search_tools(self, query: str, embedder: Callable[[str], List[float]] | None = None, top_k: int = 5) -> List[ToolMetadata]:
        """
        Searches tools using semantic similarity if an embedder is provided,
        otherwise falls back to keyword matching.
        """
        all_tools = self.list_tools()
        if not all_tools:
            return []
            
        if not embedder:
            # Fallback to keyword search
            query_lower = query.lower()
            results = []
            for tool in all_tools:
                # Weighted search: name is more important
                score = 0
                if query_lower in tool.spec.name.lower(): score += 3
                if query_lower in tool.spec.docstring.lower(): score += 1
                for kw in query_lower.split():
                    if kw in tool.spec.name.lower(): score += 1
                
                if score > 0:
                    results.append((score, tool))
            
            results.sort(key=lambda x: x[0], reverse=True)
            return [r[1] for r in results[:top_k]]

        # Semantic search
        query_embedding = embedder(query)
        
        # Load embedding cache
        cache_path = self.root / "embeddings_cache.json"
        cache = {}
        if cache_path.exists():
            try:
                cache = json.loads(cache_path.read_text())
            except: pass
            
        tool_scores = []
        dirty = False
        
        for tool in all_tools:
            # content to embed
            text = f"{tool.spec.name}: {tool.spec.docstring}"
            tool_hash = _hash_payload(text) # Use existing hash function
            
            if tool_hash in cache:
                embedding = cache[tool_hash]
            else:
                embedding = embedder(text)
                cache[tool_hash] = embedding
                dirty = True
            
            score = self._cosine_similarity(query_embedding, embedding)
            tool_scores.append((score, tool))
            
        if dirty:
             cache_path.write_text(json.dumps(cache))
             
        tool_scores.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in tool_scores[:top_k]]

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm_v1 = math.sqrt(sum(a * a for a in v1))
        norm_v2 = math.sqrt(sum(a * a for a in v2))
        return dot_product / (norm_v1 * norm_v2) if norm_v1 > 0 and norm_v2 > 0 else 0.0

    def list_tools(self) -> List[ToolMetadata]:


        """Returns metadata for all tools in the registry."""


        tools = []


        if not self.root.exists():


            return tools


        


        for tool_id_dir in self.root.iterdir():


            if tool_id_dir.is_dir():


                metadata = self.load(tool_id_dir.name)


                if metadata:


                    tools.append(metadata)


        return tools





    def get_all_artifact_paths(self) -> Set[Path]:


        promoted_paths = set()


        if not self.root.exists():


            return promoted_paths


            


        for tool_id_dir in self.root.iterdir():


            if tool_id_dir.is_dir():


                metadata = self.load(tool_id_dir.name)


                if metadata:


                    promoted_paths.add(metadata.source_path.resolve())


                    promoted_paths.add(metadata.tests_path.resolve())


        return promoted_paths