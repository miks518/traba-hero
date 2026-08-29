import React, { useState, useEffect, useCallback, useRef } from 'react';
import { captureElementRegion } from '../../lib/capture';
import type { PickerMessage, SelectedElement } from '../../../../types/picker';

export interface PickerButtonProps {
  forceActivate?: number;
  forceCancel?: number;
  forceManualCrop?: number;
  forceCropCancel?: number;
  onActiveChange?: (active: boolean) => void;
  onActivatingChange?: (activating: boolean) => void;
  onCropActiveChange?: (active: boolean) => void;
  onCropActivatingChange?: (activating: boolean) => void;
  onSelectionChange?: (hasSelection: boolean) => void;
  onScreenshotReady?: (screenshot: string) => void;
}

export function PickerButton({
  forceActivate = 0,
  forceCancel = 0,
  forceManualCrop = 0,
  forceCropCancel = 0,
  onActiveChange,
  onActivatingChange,
  onCropActiveChange,
  onCropActivatingChange,
  onSelectionChange,
  onScreenshotReady,
}: PickerButtonProps) {
  const [state, setState] = useState<'idle' | 'activating' | 'active'>('idle');
  const [cropState, setCropState] = useState<'idle' | 'activating' | 'active'>('idle');

  const prevActivate = useRef(forceActivate);
  const prevCancel = useRef(forceCancel);
  const prevManualCrop = useRef(forceManualCrop);
  const prevCropCancel = useRef(forceCropCancel);

  const reset = useCallback(() => {
    setState('idle');
    setCropState('idle');
    onActiveChange?.(false);
    onActivatingChange?.(false);
    onCropActiveChange?.(false);
    onCropActivatingChange?.(false);
    onSelectionChange?.(false);
  }, [onActiveChange, onActivatingChange, onCropActiveChange, onCropActivatingChange, onSelectionChange]);

  const handleElementSelected = useCallback((el: SelectedElement) => {
    setState('idle');
    setCropState('idle');
    onActiveChange?.(false);
    onActivatingChange?.(false);
    onCropActiveChange?.(false);
    onCropActivatingChange?.(false);
    onSelectionChange?.(true);

    captureElementRegion(el.bounds).then((dataUrl) => {
      onScreenshotReady?.(dataUrl);
    }).catch((err) => { console.warn('PickerButton:', err); });
  }, [onActiveChange, onActivatingChange, onCropActiveChange, onCropActivatingChange, onSelectionChange, onScreenshotReady]);

  useEffect(() => {
    function handler(msg: PickerMessage) {
      if (msg.source !== 'trabahero-picker') return;

      switch (msg.action) {
        case 'ELEMENT_SELECTED':
        case 'AREA_SELECTED':
          if (msg.payload) {
            handleElementSelected(msg.payload);
          }
          break;
        case 'PICKER_DEACTIVATED':
          reset();
          break;
      }
    }

    browser.runtime.onMessage.addListener(handler);
    return () => browser.runtime.onMessage.removeListener(handler);
  }, [handleElementSelected, reset]);

  const activate = useCallback(async () => {
    if (cropState !== 'idle') {
      const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
      if (tab?.id) {
        browser.tabs.sendMessage(tab.id, {
          source: 'trabahero-picker', action: 'STOP_MANUAL_CROP',
        }).catch((err) => { console.warn('PickerButton:', err); });
      }
      setCropState('idle');
      onCropActiveChange?.(false);
      onCropActivatingChange?.(false);
    }
    setState('activating');
    onActivatingChange?.(true);
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) { setState('idle'); onActivatingChange?.(false); return; }
    try {
      const resp = await browser.tabs.sendMessage(tab.id, {
        source: 'trabahero-picker', action: 'START_ELEMENT_PICKER',
      });
      if (resp?.action === 'PICKER_ACTIVATED') {
        setState('active');
        onActiveChange?.(true);
        onActivatingChange?.(false);
      } else {
        setState('idle');
        onActivatingChange?.(false);
      }
    } catch {
      setState('idle');
      onActivatingChange?.(false);
    }
  }, [cropState, onActiveChange, onActivatingChange, onCropActiveChange, onCropActivatingChange]);

  const activateManualCrop = useCallback(async () => {
    if (state !== 'idle') {
      const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
      if (tab?.id) {
        browser.tabs.sendMessage(tab.id, {
          source: 'trabahero-picker', action: 'STOP_ELEMENT_PICKER',
        }).catch((err) => { console.warn('PickerButton:', err); });
      }
      setState('idle');
      onActiveChange?.(false);
      onActivatingChange?.(false);
    }
    setCropState('activating');
    onCropActivatingChange?.(true);
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) { setCropState('idle'); onCropActivatingChange?.(false); return; }
    try {
      const resp = await browser.tabs.sendMessage(tab.id, {
        source: 'trabahero-picker', action: 'START_MANUAL_CROP',
      });
      if (resp?.action === 'MANUAL_CROP_ACTIVATED') {
        setCropState('active');
        onCropActiveChange?.(true);
        onCropActivatingChange?.(false);
      } else {
        setCropState('idle');
        onCropActivatingChange?.(false);
      }
    } catch {
      setCropState('idle');
      onCropActivatingChange?.(false);
    }
  }, [state, onActiveChange, onActivatingChange, onCropActiveChange, onCropActivatingChange]);

  const cancel = useCallback(async () => {
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
    if (tab?.id) {
      browser.tabs.sendMessage(tab.id, {
        source: 'trabahero-picker', action: 'STOP_ELEMENT_PICKER',
      }).catch((err) => { console.warn('PickerButton:', err); });
    }
    reset();
  }, [reset]);

  const cancelManualCrop = useCallback(async () => {
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
    if (tab?.id) {
      browser.tabs.sendMessage(tab.id, {
        source: 'trabahero-picker', action: 'STOP_MANUAL_CROP',
      }).catch((err) => { console.warn('PickerButton:', err); });
    }
    setCropState('idle');
    onCropActiveChange?.(false);
    onCropActivatingChange?.(false);
  }, [onCropActiveChange, onCropActivatingChange]);

  useEffect(() => {
    if (forceActivate > 0 && forceActivate !== prevActivate.current) {
      prevActivate.current = forceActivate;
      activate();
    }
  }, [forceActivate, activate]);

  useEffect(() => {
    if (forceCancel > 0 && forceCancel !== prevCancel.current) {
      prevCancel.current = forceCancel;
      cancel();
    }
  }, [forceCancel, cancel]);

  useEffect(() => {
    if (forceManualCrop > 0 && forceManualCrop !== prevManualCrop.current) {
      prevManualCrop.current = forceManualCrop;
      activateManualCrop();
    }
  }, [forceManualCrop, activateManualCrop]);

  useEffect(() => {
    if (forceCropCancel > 0 && forceCropCancel !== prevCropCancel.current) {
      prevCropCancel.current = forceCropCancel;
      cancelManualCrop();
    }
  }, [forceCropCancel, cancelManualCrop]);

  return null;
}

export default PickerButton;