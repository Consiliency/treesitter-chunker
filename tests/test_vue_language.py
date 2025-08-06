"""Comprehensive tests for Vue language support."""

from chunker import chunk_file
from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.vue import VuePlugin


class TestVueBasicChunking:
    """Test basic Vue SFC chunking functionality."""

    @staticmethod
    def test_simple_component(tmp_path):
        """Test basic Vue component structure."""
        src = tmp_path / "HelloWorld.vue"
        src.write_text(
            """<template>
  <div class="hello">
    <h1>{{ message }}</h1>
    <button @click="increment">Count: {{ count }}</button>
  </div>
</template>

<script>
export default {
  name: 'HelloWorld',
  data() {
    return {
      message: 'Hello Vue!',
      count: 0
    }
  },
  methods: {
    increment() {
      this.count++
    }
  }
}
</script>

<style scoped>
.hello {
  font-family: Arial, sans-serif;
  text-align: center;
}
h1 {
  color: #42b883;
}
</style>
""",
        )
        chunks = chunk_file(src, "vue")
        assert len(chunks) >= 3
        template_chunks = [c for c in chunks if c.node_type == "template_element"]
        assert len(template_chunks) >= 1
        assert any("{{ message }}" in c.content for c in template_chunks)
        script_chunks = [c for c in chunks if c.node_type == "script_element"]
        assert len(script_chunks) >= 1
        assert any("HelloWorld" in c.content for c in script_chunks)
        style_chunks = [c for c in chunks if c.node_type == "style_element"]
        assert len(style_chunks) >= 1
        assert any("scoped" in c.content for c in style_chunks)
        component_chunks = [c for c in chunks if c.node_type == "component_definition"]
        assert len(component_chunks) >= 1

    @staticmethod
    def test_composition_api(tmp_path):
        """Test Vue 3 Composition API."""
        src = tmp_path / "CompositionComponent.vue"
        src.write_text(
            """<template>
  <div>
    <input v-model="searchQuery" placeholder="Search...">
    <ul>
      <li v-for="item in filteredItems" :key="item.id">
        {{ item.name }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'

const searchQuery = ref('')
const items = ref([])

const filteredItems = computed(() => {
  return items.value.filter(item =>
    item.name.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

watch(searchQuery, (newValue) => {
  console.log('Search query changed:', newValue)
})

onMounted(async () => {
  const response = await fetch('/api/items')
  items.value = await response.json()
})

function clearSearch() {
  searchQuery.value = ''
}
</script>

<style lang="scss">
$primary-color: #42b883;

div {
  padding: 20px;

  input {
    width: 100%;
    padding: 10px;
    border: 1px solid $primary-color;
  }
}
</style>
""",
        )
        chunks = chunk_file(src, "vue")
        script_chunks = [c for c in chunks if c.node_type == "script_element"]
        assert any("setup" in c.content for c in script_chunks)
        style_chunks = [c for c in chunks if c.node_type == "style_element"]
        assert any('lang="scss"' in c.content for c in style_chunks)

    @staticmethod
    def test_vue_with_typescript(tmp_path):
        """Test Vue component with TypeScript."""
        src = tmp_path / "TypedComponent.vue"
        src.write_text(
            """<template>
  <div class="user-profile">
    <h2>{{ user.name }}</h2>
    <p>{{ user.email }}</p>
  </div>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue'

interface User {
  id: number
  name: string
  email: string
}

export default defineComponent({
  name: 'UserProfile',
  props: {
    user: {
      type: Object as PropType<User>,
      required: true
    }
  },
  emits: ['update', 'delete'],
  setup(props, { emit }) {
    const updateUser = () => {
      emit('update', props.user.id)
    }

    return {
      updateUser
    }
  }
})
</script>

<style>
.user-profile {
  border: 1px solid #ccc;
  padding: 20px;
}
</style>
""",
        )
        chunks = chunk_file(src, "vue")
        script_chunks = [c for c in chunks if c.node_type == "script_element"]
        assert any('lang="ts"' in c.content for c in script_chunks)
        component_chunks = [c for c in chunks if c.node_type == "component_definition"]
        assert any("defineComponent" in c.content for c in component_chunks)

    @staticmethod
    def test_template_directives(tmp_path):
        """Test Vue template directives."""
        src = tmp_path / "DirectivesDemo.vue"
        src.write_text(
            """<template>
  <div>
    <div v-if="isVisible">Conditional content</div>
    <div v-else>Alternative content</div>

    <ul>
      <li v-for="(item, index) in items" :key="item.id">
        {{ index + 1 }}. {{ item.name }}
      </li>
    </ul>

    <div v-show="showDetails">Details section</div>

    <input v-model="inputValue" @input="handleInput">

    <button @click="handleClick" :disabled="isDisabled">
      Click me
    </button>

    <custom-directive v-custom="directiveValue" />
  </div>
</template>

<script>
export default {
  name: 'DirectivesDemo',
  data() {
    return {
      isVisible: true,
      showDetails: false,
      items: [],
      inputValue: '',
      isDisabled: false,
      directiveValue: 'test'
    }
  },
  methods: {
    handleClick() {
      console.log('Clicked!')
    },
    handleInput(e) {
      console.log('Input:', e.target.value)
    }
  }
}
</script>
""",
        )
        chunks = chunk_file(src, "vue")
        template_chunks = [c for c in chunks if c.node_type == "template_element"]
        assert len(template_chunks) >= 1
        template_content = template_chunks[0].content
        assert "v-if" in template_content
        assert "v-for" in template_content
        assert "v-show" in template_content
        assert "v-model" in template_content


class TestVueContractCompliance:
    """Test ExtendedLanguagePluginContract implementation."""

    @classmethod
    def test_implements_contract(cls):
        """Test that VuePlugin implements the contract."""
        plugin = VuePlugin()
        assert isinstance(plugin, ExtendedLanguagePluginContract)

    @staticmethod
    def test_get_semantic_chunks():
        """Test get_semantic_chunks method."""
        plugin = VuePlugin()

        class MockNode:

            def __init__(self, node_type, start=0, end=1):
                self.type = node_type
                self.start_byte = start
                self.end_byte = end
                self.start_point = 0, 0
                self.end_point = 0, end
                self.children = []

        root = MockNode("document")
        template_node = MockNode("template_element", 0, 50)
        script_node = MockNode("script_element", 51, 100)
        style_node = MockNode("style_element", 101, 150)
        root.children = [template_node, script_node, style_node]
        source = b"<template></template><script></script><style></style>"
        chunks = plugin.get_semantic_chunks(root, source)
        assert len(chunks) >= 3
        assert any(chunk["type"] == "template_element" for chunk in chunks)
        assert any(chunk["type"] == "script_element" for chunk in chunks)
        assert any(chunk["type"] == "style_element" for chunk in chunks)

    @classmethod
    def test_get_chunk_node_types(cls):
        """Test get_chunk_node_types method."""
        plugin = VuePlugin()
        node_types = plugin.get_chunk_node_types()
        assert isinstance(node_types, set)
        assert "template_element" in node_types
        assert "script_element" in node_types
        assert "style_element" in node_types

    @staticmethod
    def test_should_chunk_node():
        """Test should_chunk_node method."""
        plugin = VuePlugin()

        class MockNode:

            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        assert plugin.should_chunk_node(MockNode("template_element"))
        assert plugin.should_chunk_node(MockNode("script_element"))
        assert plugin.should_chunk_node(MockNode("style_element"))
        assert not plugin.should_chunk_node(MockNode("text"))
        assert not plugin.should_chunk_node(MockNode("comment"))

    @staticmethod
    def test_get_node_context():
        """Test get_node_context method."""
        plugin = VuePlugin()

        class MockNode:

            def __init__(self, node_type):
                self.type = node_type
                self.children = []

        node = MockNode("template_element")
        context = plugin.get_node_context(node, b"<template></template>")
        assert context is not None
        assert "template" in context


class TestVueEdgeCases:
    """Test edge cases in Vue parsing."""

    @staticmethod
    def test_empty_file(tmp_path):
        """Test empty Vue file."""
        src = tmp_path / "Empty.vue"
        src.write_text("")
        chunks = chunk_file(src, "vue")
        assert len(chunks) == 0

    @staticmethod
    def test_template_only(tmp_path):
        """Test Vue file with only template."""
        src = tmp_path / "TemplateOnly.vue"
        src.write_text(
            "<template>\n  <div>Template only component</div>\n</template>\n",
        )
        chunks = chunk_file(src, "vue")
        assert len(chunks) >= 1
        assert all(c.node_type == "template_element" for c in chunks)

    @staticmethod
    def test_multiple_script_blocks(tmp_path):
        """Test Vue file with multiple script blocks."""
        src = tmp_path / "MultiScript.vue"
        src.write_text(
            """<script>
// Regular script for component options
export default {
  name: 'MultiScript'
}
</script>

<script setup>
// Setup script for Composition API
import { ref } from 'vue'

const count = ref(0)
</script>

<template>
  <div>{{ count }}</div>
</template>
""",
        )
        chunks = chunk_file(src, "vue")
        script_chunks = [c for c in chunks if c.node_type == "script_element"]
        assert len(script_chunks) >= 2

    @staticmethod
    def test_slots_and_scoped_slots(tmp_path):
        """Test Vue component with slots."""
        src = tmp_path / "SlotComponent.vue"
        src.write_text(
            """<template>
  <div class="card">
    <header>
      <slot name="header">Default header</slot>
    </header>

    <main>
      <slot>Default content</slot>
    </main>

    <footer>
      <slot name="footer" :user="currentUser">
        Default footer for {{ currentUser.name }}
      </slot>
    </footer>
  </div>
</template>

<script>
export default {
  name: 'Card',
  data() {
    return {
      currentUser: { name: 'Guest' }
    }
  }
}
</script>
""",
        )
        chunks = chunk_file(src, "vue")
        template_chunks = [c for c in chunks if c.node_type == "template_element"]
        assert len(template_chunks) >= 1
        assert "slot" in template_chunks[0].content

    @staticmethod
    def test_custom_blocks(tmp_path):
        """Test Vue file with custom blocks."""
        src = tmp_path / "CustomBlocks.vue"
        src.write_text(
            """<template>
  <div>{{ t('hello') }}</div>
</template>

<script>
export default {
  name: 'I18nComponent'
}
</script>

<i18n>
{
  "en": {
    "hello": "Hello World"
  },
  "es": {
    "hello": "Hola Mundo"
  }
}
</i18n>

<docs>
# I18n Component

This component demonstrates internationalization.
</docs>
""",
        )
        chunks = chunk_file(src, "vue")
        assert any(c.node_type == "template_element" for c in chunks)
        assert any(c.node_type == "script_element" for c in chunks)

    @staticmethod
    def test_inline_templates(tmp_path):
        """Test Vue component with inline template."""
        src = tmp_path / "InlineTemplate.vue"
        src.write_text(
            """<script>
export default {
  name: 'InlineTemplate',
  template: `
    <div>
      <h1>{{ title }}</h1>
      <p>{{ content }}</p>
    </div>
  `,
  data() {
    return {
      title: 'Inline Template',
      content: 'This template is defined in the script section'
    }
  }
}
</script>

<style>
div {
  padding: 20px;
}
</style>
""",
        )
        chunks = chunk_file(src, "vue")
        assert any(c.node_type == "script_element" for c in chunks)
        assert any(c.node_type == "style_element" for c in chunks)

    @staticmethod
    def test_functional_components(tmp_path):
        """Test functional Vue components."""
        src = tmp_path / "FunctionalComponent.vue"
        src.write_text(
            """<template functional>
  <div class="functional-component">
    <h2>{{ props.title }}</h2>
    <p>{{ props.message }}</p>
  </div>
</template>

<script>
export default {
  name: 'FunctionalComponent',
  props: {
    title: String,
    message: String
  }
}
</script>
""",
        )
        chunks = chunk_file(src, "vue")
        template_chunks = [c for c in chunks if c.node_type == "template_element"]
        assert len(template_chunks) >= 1
        assert "functional" in template_chunks[0].content
