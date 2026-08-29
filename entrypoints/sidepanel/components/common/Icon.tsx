import React from 'react';

export type IconName =
  | 'security'
  | 'description'
  | 'help'
  | 'settings'
  | 'contact_support'
  | 'open_in_new'
  | 'warning'
  | 'bolt'
  | 'refresh'
  | 'flag'
  | 'alternate_email'
  | 'payments'
  | 'history_edu'
  | 'phone_disabled'
  | 'picture_as_pdf'
  | 'edit'
  | 'add'
  | 'check_circle'
  | 'rocket_launch'
  | 'close'
  | 'touch_app'
  | 'crop'
  | 'info'
  | 'upload_file'
  | 'delete'
  | 'work'
  | 'dark_mode'
  | 'light_mode'
  | 'smart_toy'
  | 'travel_explore'
  | 'chevron_left'
  | 'chevron_right'
  | 'keyboard_arrow_down'
  | 'history'
  | 'handshake'
  | 'search'
  | 'architecture'
  | 'database'
  | 'shield_person'
  | 'timer'
  | 'calendar_month'
  | 'lock'
  | 'business'
  | 'tips_and_updates'
  | 'arrow_right';

export interface IconProps extends React.HTMLAttributes<HTMLSpanElement> {
  name: IconName;
  fill?: boolean;
  filled?: boolean;
}

export function Icon({
  name,
  fill = false,
  filled = false,
  className = '',
  style = {},
  ...rest
}: IconProps) {
  return (
    <span
      className={'material-symbols-outlined ' + className}
      style={{
        fontVariationSettings: filled || fill ? '\"FILL\" 1' : '\"FILL\" 0',
        ...style,
      }}
      {...rest}
    >
      {name}
    </span>
  );
}

export default Icon;
