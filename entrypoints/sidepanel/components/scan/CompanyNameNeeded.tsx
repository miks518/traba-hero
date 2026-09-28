import React from 'react';
import { Icon } from '../common';

/**
 * Shown when a posting names no employer, so external verification cannot run.
 *
 * A missing name is a missing input, not a finding about the post, so this is
 * deliberately NOT styled like the result containers: the border is dashed where
 * every result card uses a solid one, which reads as "not filled in" rather than
 * as one more thing we found out.
 *
 * There is no text input on purpose. A typed company name would flow straight
 * into the verification prompt, which produces a verdict naming a real company.
 */
export function CompanyNameNeeded() {
  return (
    <section className="rounded-xl border border-dashed border-outline/45 bg-surface-container-lowest p-4 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Icon name="help" className="text-outline" />
        <h3 className="text-label-md font-bold text-on-surface">Company name needed</h3>
      </div>

      <p className="text-body-sm text-on-surface-variant leading-relaxed">
        We read this post and checked it on its own. It does not name a company, so there is
        nothing for us to look up &mdash; we could not confirm that the employer is real or
        registered. That is a gap in what we could check, not a warning about this post.
      </p>

      <div className="flex items-start gap-2 pt-0.5">
        <Icon name="touch_app" className="text-outline text-base shrink-0 mt-0.5" />
        <p className="text-body-sm text-on-surface-variant leading-relaxed">
          If the company&rsquo;s logo, letterhead, or sender name appears elsewhere on the page,
          pick that part and scan it again &mdash; the name is usually there.
        </p>
      </div>
    </section>
  );
}

export default CompanyNameNeeded;
