"""Comprehensive tests for Svelte language support."""

from chunker import chunk_file
from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.svelte import SveltePlugin


class TestSvelteBasicChunking:
    """Test basic Svelte component chunking functionality."""

    def test_simple_component(self, tmp_path):
        """Test basic Svelte component structure."""
        src = tmp_path / "HelloWorld.svelte"
        src.write_text(
            """<script>
  let name = 'world';
  let count = 0;

  function increment() {
    count += 1;
  }
</script>

<main>
  <h1>Hello {name}!</h1>
  <button on:click={increment}>
    Clicked {count} {count === 1 ? 'time' : 'times'}
  </button>
</main>

<style>
  main {
    text-align: center;
    padding: 1em;
  }

  h1 {
    color: #ff3e00;
  }
</style>
""",
        )
        chunks = chunk_file(src, "svelte")
        assert len(chunks) >= 2

        # Check for script section
        script_chunks = [
            c for c in chunks if c.node_type in {"script_element", "instance_script"}
        ]
        assert len(script_chunks) >= 1
        assert any("count" in c.content for c in script_chunks)

        # Check for style section
        style_chunks = [c for c in chunks if c.node_type == "style_element"]
        assert len(style_chunks) >= 1
        assert any("#ff3e00" in c.content for c in style_chunks)

    def test_reactive_statements(self, tmp_path):
        """Test Svelte reactive statements."""
        src = tmp_path / "Reactive.svelte"
        src.write_text(
            """<script>
  let count = 0;
  let doubled = 0;
  let quadrupled = 0;

  // Reactive statement
  $: doubled = count * 2;

  // Reactive block
  $: {
    console.log(`count is ${count}`);
    quadrupled = doubled * 2;
  }

  // Reactive function call
  $: if (count >= 10) {
    alert('Count is getting high!');
  }

  function increment() {
    count += 1;
  }
</script>

<button on:click={increment}>
  Count: {count}, Doubled: {doubled}, Quadrupled: {quadrupled}
</button>
""",
        )
        chunks = chunk_file(src, "svelte")

        # Check for reactive statements
        reactive_chunks = [
            c
            for c in chunks
            if c.node_type == "reactive_statement" or "$:" in c.content
        ]
        assert len(reactive_chunks) >= 3
        assert any("doubled = count * 2" in c.content for c in chunks)

    def test_control_flow_blocks(self, tmp_path):
        """Test Svelte control flow blocks."""
        src = tmp_path / "ControlFlow.svelte"
        src.write_text(
            """<script>
  let items = ['Apple', 'Banana', 'Cherry'];
  let showItems = true;
  let promise = fetchData();

  async function fetchData() {
    await new Promise(r => setTimeout(r, 1000));
    return { data: 'Loaded!' };
  }
</script>

{#if showItems}
  <h2>Fruit List</h2>

  {#each items as item, index}
    <div>
      {index + 1}. {item}
    </div>
  {:else}
    <p>No items to display</p>
  {/each}
{:else}
  <p>Items hidden</p>
{/if}

{#await promise}
  <p>Loading...</p>
{:then result}
  <p>Result: {result.data}</p>
{:catch error}
  <p>Error: {error.message}</p>
{/await}

{#key items.length}
  <p>Total items: {items.length}</p>
{/key}
""",
        )
        chunks = chunk_file(src, "svelte")

        # Check for control flow blocks
        if_chunks = [c for c in chunks if c.node_type == "if_block"]
        each_chunks = [c for c in chunks if c.node_type == "each_block"]
        await_chunks = [c for c in chunks if c.node_type == "await_block"]
        key_chunks = [c for c in chunks if c.node_type == "key_block"]

        assert len(if_chunks) >= 1
        assert len(each_chunks) >= 1
        assert len(await_chunks) >= 1
        assert len(key_chunks) >= 1

    def test_module_and_instance_scripts(self, tmp_path):
        """Test module context script."""
        src = tmp_path / "ModuleScript.svelte"
        src.write_text(
            """<script context="module">
  let totalInstances = 0;

  export function getInstanceCount() {
    return totalInstances;
  }
</script>

<script>
  import { onMount, onDestroy } from 'svelte';

  export let title = 'Default Title';

  onMount(() => {
    totalInstances += 1;
  });

  onDestroy(() => {
    totalInstances -= 1;
  });
</script>

<h1>{title}</h1>
<p>Total instances: {totalInstances}</p>
""",
        )
        chunks = chunk_file(src, "svelte")

        # Check for module and instance scripts
        module_chunks = [
            c
            for c in chunks
            if c.node_type == "module_script" or ('context="module"' in c.content)
        ]
        instance_chunks = [
            c
            for c in chunks
            if c.node_type == "instance_script"
            or (c.node_type == "script_element" and 'context="module"' not in c.content)
        ]

        assert len(module_chunks) >= 1
        assert len(instance_chunks) >= 1
        assert any("totalInstances" in c.content for c in module_chunks)
        assert any("onMount" in c.content for c in instance_chunks)

    def test_stores_and_bindings(self, tmp_path):
        """Test Svelte stores and bindings."""
        src = tmp_path / "Stores.svelte"
        src.write_text(
            """<script>
  import { writable, derived } from 'svelte/store';

  const count = writable(0);
  const doubled = derived(count, $count => $count * 2);

  let inputValue = '';
  let checked = false;

  function increment() {
    count.update(n => n + 1);
  }
</script>

<input bind:value={inputValue} placeholder="Type something...">
<input type="checkbox" bind:checked>

<p>Input: {inputValue}</p>
<p>Checked: {checked}</p>

<button on:click={increment}>
  Count: {$count}, Doubled: {$doubled}
</button>

<style>
  input {
    margin: 10px 0;
  }
</style>
""",
        )
        chunks = chunk_file(src, "svelte")

        # Check for script with stores
        script_chunks = [
            c for c in chunks if c.node_type in ["script_element", "instance_script"]
        ]
        assert any("writable" in c.content for c in script_chunks)
        assert any("derived" in c.content for c in script_chunks)


class TestSvelteContractCompliance:
    """Test ExtendedLanguagePluginContract implementation."""

    def test_implements_contract(self):
        """Test that SveltePlugin implements the contract."""
        plugin = SveltePlugin()
        assert isinstance(plugin, ExtendedLanguagePluginContract)

    def test_get_semantic_chunks(self):
        """Test get_semantic_chunks method."""
        plugin = SveltePlugin()

        # Mock node structure
        class MockNode:
            def __init__(self, node_type, start=0, end=1):
                self.type = node_type
                self.start_byte = start
                self.end_byte = end
                self.start_point = (0, 0)
                self.end_point = (0, end)
                self.children = []

        root = MockNode("document")
        script_node = MockNode("script_element", 0, 50)
        style_node = MockNode("style_element", 51, 100)
        if_node = MockNode("if_block", 101, 150)
        root.children = [script_node, style_node, if_node]

        source = b"<script></script><style></style>{#if true}{/if}"
        chunks = plugin.get_semantic_chunks(root, source)

        assert len(chunks) >= 3
        assert any(chunk["type"] == "script_element" for chunk in chunks)
        assert any(chunk["type"] == "style_element" for chunk in chunks)
        assert any(chunk["type"] == "if_block" for chunk in chunks)

    def test_get_chunk_node_types(self):
        """Test get_chunk_node_types method."""
        plugin = SveltePlugin()
        node_types = plugin.get_chunk_node_types()

        assert isinstance(node_types, set)
        assert "script_element" in node_types
        assert "style_element" in node_types
        assert "if_block" in node_types
        assert "each_block" in node_types

    def test_should_chunk_node(self):
        """Test should_chunk_node method."""
        plugin = SveltePlugin()

        # Mock node
        class MockNode:
            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        # Test chunk nodes
        assert plugin.should_chunk_node(MockNode("script_element"))
        assert plugin.should_chunk_node(MockNode("style_element"))
        assert plugin.should_chunk_node(MockNode("if_block"))
        assert plugin.should_chunk_node(MockNode("each_block"))

        # Test non-chunk nodes
        assert not plugin.should_chunk_node(MockNode("text"))
        assert not plugin.should_chunk_node(MockNode("comment"))

    def test_get_node_context(self):
        """Test get_node_context method."""
        plugin = SveltePlugin()

        # Mock node
        class MockNode:
            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        # Test context extraction
        node = MockNode("script_element")
        context = plugin.get_node_context(node, b'<script context="module"></script>')
        assert context is not None
        assert "script" in context


class TestSvelteEdgeCases:
    """Test edge cases in Svelte parsing."""

    def test_empty_file(self, tmp_path):
        """Test empty Svelte file."""
        src = tmp_path / "Empty.svelte"
        src.write_text("")
        chunks = chunk_file(src, "svelte")
        assert len(chunks) == 0

    def test_html_only(self, tmp_path):
        """Test Svelte file with only HTML."""
        src = tmp_path / "HtmlOnly.svelte"
        src.write_text(
            """<h1>Static HTML</h1>
<p>No scripts or styles</p>
""",
        )
        chunks = chunk_file(src, "svelte")
        # HTML-only content might not produce chunks unless it has control flow
        assert len(chunks) == 0

    def test_typescript_support(self, tmp_path):
        """Test Svelte with TypeScript."""
        src = tmp_path / "TypeScript.svelte"
        src.write_text(
            """<script lang="ts">
  export let count: number = 0;
  export let name: string = 'World';

  interface User {
    id: number;
    name: string;
    email: string;
  }

  let user: User = {
    id: 1,
    name: 'John',
    email: 'john@example.com'
  };

  function increment(): void {
    count += 1;
  }
</script>

<h1>Hello {name}!</h1>
<p>Count: {count}</p>
<p>User: {user.name} ({user.email})</p>
<button on:click={increment}>Increment</button>
""",
        )
        chunks = chunk_file(src, "svelte")

        # Check for TypeScript script
        script_chunks = [
            c for c in chunks if c.node_type in ["script_element", "instance_script"]
        ]
        assert len(script_chunks) >= 1
        assert any('lang="ts"' in c.content for c in script_chunks)

    def test_slots(self, tmp_path):
        """Test Svelte component with slots."""
        src = tmp_path / "SlotComponent.svelte"
        src.write_text(
            """<script>
  export let title = 'Default Title';
</script>

<div class="card">
  <header>
    <slot name="header">
      <h2>{title}</h2>
    </slot>
  </header>

  <main>
    <slot>Default content</slot>
  </main>

  <footer>
    <slot name="footer" count={42}>
      <p>Default footer</p>
    </slot>
  </footer>
</div>

<style>
  .card {
    border: 1px solid #ccc;
    padding: 1rem;
  }
</style>
""",
        )
        chunks = chunk_file(src, "svelte")

        # Should have script and style chunks
        assert any(c.node_type in ["script_element", "instance_script"] for c in chunks)
        assert any(c.node_type == "style_element" for c in chunks)

    def test_event_handlers_and_modifiers(self, tmp_path):
        """Test various event handlers and modifiers."""
        src = tmp_path / "Events.svelte"
        src.write_text(
            """<script>
  let message = '';

  function handleClick(event) {
    console.log('Clicked!', event);
  }

  function handleKeydown(event) {
    if (event.key === 'Enter') {
      message = 'Enter pressed!';
    }
  }

  function handleSubmit() {
    console.log('Form submitted');
  }
</script>

<button on:click={handleClick}>Simple click</button>
<button on:click|once={handleClick}>Click once</button>
<button on:click|preventDefault={handleClick}>Prevent default</button>
<button on:click|stopPropagation={handleClick}>Stop propagation</button>

<input on:keydown={handleKeydown} placeholder="Press Enter">

<form on:submit|preventDefault={handleSubmit}>
  <button type="submit">Submit</button>
</form>

<div on:click|self={() => console.log('Self only')}>
  <button>This won't trigger parent</button>
</div>

{#if message}
  <p>{message}</p>
{/if}
""",
        )
        chunks = chunk_file(src, "svelte")

        # Check for script and control flow
        script_chunks = [
            c for c in chunks if c.node_type in ["script_element", "instance_script"]
        ]
        if_chunks = [c for c in chunks if c.node_type == "if_block"]

        assert len(script_chunks) >= 1
        assert len(if_chunks) >= 1

    def test_animations_and_transitions(self, tmp_path):
        """Test Svelte animations and transitions."""
        src = tmp_path / "Animations.svelte"
        src.write_text(
            """<script>
  import { fade, fly, slide } from 'svelte/transition';
  import { flip } from 'svelte/animate';

  let visible = true;
  let items = [1, 2, 3, 4, 5];

  function addItem() {
    items = [...items, items.length + 1];
  }

  function removeItem(item) {
    items = items.filter(i => i !== item);
  }
</script>

<button on:click={() => visible = !visible}>
  Toggle
</button>

{#if visible}
  <div transition:fade>Fades in and out</div>
  <div in:fly="{{ y: 200, duration: 500 }}" out:slide>
    Flies in, slides out
  </div>
{/if}

{#each items as item (item)}
  <div animate:flip="{{ duration: 300 }}">
    Item {item}
    <button on:click={() => removeItem(item)}>Remove</button>
  </div>
{/each}

<button on:click={addItem}>Add Item</button>
""",
        )
        chunks = chunk_file(src, "svelte")

        # Check for control flow blocks
        if_chunks = [c for c in chunks if c.node_type == "if_block"]
        each_chunks = [c for c in chunks if c.node_type == "each_block"]

        assert len(if_chunks) >= 1
        assert len(each_chunks) >= 1

    def test_component_composition(self, tmp_path):
        """Test component imports and usage."""
        src = tmp_path / "Parent.svelte"
        src.write_text(
            """<script>
  import Child from './Child.svelte';
  import { Button } from './components';

  let items = ['A', 'B', 'C'];
  let selectedItem = null;

  function handleSelect(item) {
    selectedItem = item;
  }
</script>

<h1>Parent Component</h1>

{#each items as item}
  <Child
    {item}
    on:select={() => handleSelect(item)}
    selected={selectedItem === item}
  />
{/each}

<Button on:click={() => selectedItem = null}>
  Clear Selection
</Button>

{#if selectedItem}
  <p>Selected: {selectedItem}</p>
{/if}

<style>
  h1 {
    color: navy;
  }
</style>
""",
        )
        chunks = chunk_file(src, "svelte")

        # Check for all major sections
        script_chunks = [
            c for c in chunks if c.node_type in ["script_element", "instance_script"]
        ]
        each_chunks = [c for c in chunks if c.node_type == "each_block"]
        if_chunks = [c for c in chunks if c.node_type == "if_block"]
        style_chunks = [c for c in chunks if c.node_type == "style_element"]

        assert len(script_chunks) >= 1
        assert len(each_chunks) >= 1
        assert len(if_chunks) >= 1
        assert len(style_chunks) >= 1
