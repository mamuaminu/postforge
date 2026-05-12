'use client';

import { useEffect, useState } from 'react';
import { getSubscription } from '@/lib/api';

interface Subscription {
  plan: string;
  status: string;
  renews_at?: string;
}

const PLANS = [
  {
    name: 'Free',
    price: '$0',
    period: 'forever',
    features: ['5 posts per day', '2 platforms', 'Basic tones'],
  },
  {
    name: 'Pro',
    price: '$19',
    period: 'per month',
    features: ['Unlimited posts', 'All platforms', 'All tones', 'Priority generation'],
  },
  {
    name: 'Enterprise',
    price: '$49',
    period: 'per month',
    features: ['Everything in Pro', 'Team access', 'API access', 'Dedicated support'],
  },
];

export default function BillingPage() {
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSubscription()
      .then(setSubscription)
      .catch(() => setSubscription(null))
      .finally(() => setLoading(false));
  }, []);

  const currentPlan = subscription?.plan?.toLowerCase() || 'free';

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold" style={{ color: 'var(--text)', fontFamily: "'Fira Code', monospace" }}>
          Billing
        </h2>
        <p className="mt-1" style={{ color: 'var(--text-muted)' }}>
          Manage your subscription and billing details.
        </p>
      </div>

      {loading ? (
        <div style={{ color: 'var(--text-muted)' }}>Loading...</div>
      ) : (
        <>
          {/* Current plan banner */}
          {subscription && (
            <div
              className="rounded-xl p-6"
              style={{ background: 'var(--bg-surface)', border: '1px solid var(--accent)' }}
            >
              <h3 className="text-sm font-medium uppercase tracking-wider mb-4" style={{ color: 'var(--text-muted)' }}>
                Current Plan
              </h3>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-white font-semibold text-lg capitalize">
                    {subscription.plan} Plan
                  </span>
                  <span
                    className="text-xs font-medium px-2.5 py-1 rounded-full"
                    style={{ background: 'rgba(34,197,94,0.15)', color: 'var(--accent)' }}
                  >
                    Active
                  </span>
                </div>
                {subscription.renews_at && (
                  <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                    Renews: {new Date(subscription.renews_at).toLocaleDateString()}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Plan cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {PLANS.map((plan) => {
              const isCurrent = plan.name.toLowerCase() === currentPlan;
              return (
                <div
                  key={plan.name}
                  className="rounded-xl p-6 flex flex-col"
                  style={{
                    background: 'var(--bg-surface)',
                    border: isCurrent ? '2px solid var(--accent)' : '1px solid var(--border)',
                  }}
                >
                  <div className="mb-4">
                    <h4 className="text-lg font-semibold" style={{ color: 'var(--text)', fontFamily: "'Fira Code', monospace" }}>
                      {plan.name}
                    </h4>
                    <div className="flex items-baseline gap-1 mt-1">
                      <span className="text-2xl font-bold" style={{ color: 'var(--text)' }}>
                        {plan.price}
                      </span>
                      <span className="text-sm" style={{ color: 'var(--text-muted)' }}>
                        / {plan.period}
                      </span>
                    </div>
                  </div>

                  <ul className="space-y-2 mb-6 flex-1">
                    {plan.features.map((f) => (
                      <li key={f} className="text-sm flex items-center gap-2" style={{ color: 'var(--text-muted)' }}>
                        <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: 'var(--accent)' }}>
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        {f}
                      </li>
                    ))}
                  </ul>

                  <button
                    className="text-sm font-medium py-2 rounded-lg w-full"
                    style={{
                      background: isCurrent ? 'rgba(34,197,94,0.1)' : 'var(--accent)',
                      color: isCurrent ? 'var(--accent)' : '#fff',
                      border: isCurrent ? '1px solid var(--accent)' : 'none',
                      transition: 'all 150ms ease',
                    }}
                    onMouseEnter={(e) => {
                      if (!isCurrent) e.currentTarget.style.background = '#16a34a';
                    }}
                    onMouseLeave={(e) => {
                      if (!isCurrent) e.currentTarget.style.background = 'var(--accent)';
                    }}
                    disabled={isCurrent}
                  >
                    {isCurrent ? 'Current Plan' : plan.name === 'Free' ? 'Downgrade' : 'Upgrade'}
                  </button>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}