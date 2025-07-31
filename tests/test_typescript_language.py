"""Test TypeScript and TSX language support."""

import pytest

from chunker.core import chunk_text
from chunker.languages import language_config_registry


class TestTypeScriptLanguage:
    """Test TypeScript language chunking."""

    def test_typescript_basic_chunking(self):
        """Test basic TypeScript chunking."""
        code = """
interface User {
    id: number;
    name: string;
    email?: string;
}

class UserService {
    private users: User[] = [];

    addUser(user: User): void {
        this.users.push(user);
    }

    getUser(id: number): User | undefined {
        return this.users.find(u => u.id === id);
    }
}

async function fetchUserData(id: number): Promise<User> {
    const response = await fetch(`/api/users/${id}`);
    return response.json();
}

export { User, UserService, fetchUserData };
"""
        chunks = chunk_text(code, language="typescript")
        assert len(chunks) >= 4  # interface, class, 2 methods, function

        # Verify chunk types
        chunk_types = [chunk.metadata.get("type") for chunk in chunks]
        assert "interface_declaration" in chunk_types
        assert "class_declaration" in chunk_types
        assert "function_declaration" in chunk_types

    def test_tsx_component_chunking(self):
        """Test TSX React component chunking."""
        code = """
import React, { useState, useEffect } from 'react';

interface Props {
    title: string;
    onClose?: () => void;
}

const Modal: React.FC<Props> = ({ title, onClose }) => {
    const [isVisible, setIsVisible] = useState(true);

    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                setIsVisible(false);
                onClose?.();
            }
        };

        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, [onClose]);

    return isVisible ? (
        <div className="modal">
            <h2>{title}</h2>
            <button onClick={() => setIsVisible(false)}>Close</button>
        </div>
    ) : null;
};

export default Modal;
"""
        chunks = chunk_text(code, language="tsx")
        assert len(chunks) >= 2  # interface and component

        # Check for JSX handling
        component_chunk = next((c for c in chunks if "Modal" in c.content), None)
        assert component_chunk is not None
        assert "<div" in component_chunk.content

    def test_typescript_generics(self):
        """Test TypeScript with complex generics."""
        code = """
type Result<T, E = Error> =
    | { success: true; data: T }
    | { success: false; error: E };

function wrapPromise<T>(promise: Promise<T>): Result<T> {
    return promise
        .then(data => ({ success: true, data } as const))
        .catch(error => ({ success: false, error } as const));
}

class Container<T extends Record<string, unknown>> {
    private items: Map<keyof T, T[keyof T]> = new Map();

    get<K extends keyof T>(key: K): T[K] | undefined {
        return this.items.get(key) as T[K] | undefined;
    }

    set<K extends keyof T>(key: K, value: T[K]): void {
        this.items.set(key, value);
    }
}
"""
        chunks = chunk_text(code, language="typescript")
        assert len(chunks) >= 3  # type alias, function, class

    def test_typescript_decorators(self):
        """Test TypeScript decorators."""
        code = """
function log(target: any, propertyKey: string, descriptor: PropertyDescriptor) {
    const original = descriptor.value;
    descriptor.value = function(...args: any[]) {
        console.log(`Calling ${propertyKey} with`, args);
        return original.apply(this, args);
    };
}

@sealed
class BugReport {
    type = "report";
    title: string;

    constructor(t: string) {
        this.title = t;
    }

    @log
    print() {
        console.log(`type: ${this.type}`);
        console.log(`title: ${this.title}`);
    }
}

function sealed(constructor: Function) {
    Object.seal(constructor);
    Object.seal(constructor.prototype);
}
"""
        chunks = chunk_text(code, language="typescript")
        assert len(chunks) >= 3  # decorator functions and class

    def test_typescript_namespace(self):
        """Test TypeScript namespace chunking."""
        code = """
namespace Validation {
    export interface StringValidator {
        isAcceptable(s: string): boolean;
    }

    const lettersRegexp = /^[A-Za-z]+$/;
    const numberRegexp = /^[0-9]+$/;

    export class LettersOnlyValidator implements StringValidator {
        isAcceptable(s: string) {
            return lettersRegexp.test(s);
        }
    }

    export class ZipCodeValidator implements StringValidator {
        isAcceptable(s: string) {
            return s.length === 5 && numberRegexp.test(s);
        }
    }
}
"""
        chunks = chunk_text(code, language="typescript")
        assert len(chunks) >= 1  # namespace should be chunked

        # Verify namespace is properly captured
        namespace_chunk = next((c for c in chunks if "namespace" in c.content), None)
        assert namespace_chunk is not None

    def test_typescript_enum_chunking(self):
        """Test TypeScript enum chunking."""
        code = """
enum Direction {
    Up = 1,
    Down,
    Left,
    Right,
}

const enum FileAccess {
    None,
    Read = 1 << 1,
    Write = 1 << 2,
    ReadWrite = Read | Write,
}

enum BooleanLikeHeterogeneousEnum {
    No = 0,
    Yes = "YES",
}
"""
        chunks = chunk_text(code, language="typescript")
        assert len(chunks) >= 3  # three enums

    @pytest.mark.parametrize("file_extension", [".ts", ".tsx", ".d.ts"])
    def test_typescript_file_extensions(self, file_extension):
        """Test TypeScript file extension detection."""
        config = language_config_registry.get_for_file(f"test{file_extension}")
        assert config is not None
        assert config.name in ["typescript", "tsx"]
