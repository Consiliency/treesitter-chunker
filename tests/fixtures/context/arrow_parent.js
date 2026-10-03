import { formatName } from './format.js';

const transform = (value) => {
  const normalized = formatName(value);
  return normalized.trim();
};
