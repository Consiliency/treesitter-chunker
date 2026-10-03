<script context="module" lang="ts">
  export const answer: number = 42;
</script>
<script>
  let items = [1, 2];
  $: count = items.length;
</script>
{#each items as item}
  <p>{item}</p>
{/each}
<style lang="scss">
  p { color: red; }
</style>
