import python from '../../../data/samples/python_loop.props.json';
import newton from '../../../data/samples/newtons_second_law.props.json';
import water from '../../../data/samples/water_cycle.props.json';
import {parseRenderProps} from '../lesson/validate';

export const samples = [
  {id: 'python', subject: 'PROGRAMMING', name: 'Inside a Python loop', detail: 'Watch code turn into three simple passes.', symbol: '</>', props: parseRenderProps(python)},
  {id: 'newton', subject: 'PHYSICS', name: 'A little force. A big idea.', detail: 'See mass, force and acceleration connect.', symbol: 'F = ma', props: parseRenderProps(newton)},
  {id: 'water', subject: 'SCIENCE', name: 'The journey of a raindrop', detail: 'Follow water around a never-ending cycle.', symbol: '↻', props: parseRenderProps(water)},
] as const;
