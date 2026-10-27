import raw from './data/array-grid-demo.visual.json';
import {parseVisualFixture} from '../utils/parseVisualSpec';
import {createMockTimeline} from './index';
import {parseRenderProps} from '../lesson/validate';

// Unchanged backend-authored fixture. No inference, production cache or schema extension.
export const arrayDemoFixture = parseVisualFixture(raw);
export const arrayDemoProps = parseRenderProps({lesson: arrayDemoFixture.source,
  timeline: createMockTimeline(arrayDemoFixture), mediaBase: '', audioVariant: 'web', showCaptions: true});
