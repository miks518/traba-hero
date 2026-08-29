export interface BoundingBox {
  top: number;
  left: number;
  width: number;
  height: number;
}

export interface SelectedElement {
  tagName: string;
  id: string | null;
  className: string | null;
  text: string;
  outerHTML: string;
  bounds: BoundingBox;
}

export type PickerAction =
  | 'START_ELEMENT_PICKER'
  | 'STOP_ELEMENT_PICKER'
  | 'ELEMENT_SELECTED'
  | 'PICKER_ACTIVATED'
  | 'PICKER_DEACTIVATED'
  | 'START_MANUAL_CROP'
  | 'STOP_MANUAL_CROP'
  | 'MANUAL_CROP_ACTIVATED'
  | 'AREA_SELECTED'
  | 'PING';

export interface PickerMessage {
  source: 'trabahero-picker';
  action: PickerAction;
  payload?: SelectedElement | null;
}
