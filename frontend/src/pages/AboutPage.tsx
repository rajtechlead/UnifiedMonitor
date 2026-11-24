import { Mail, ShieldCheck, Globe, LifeBuoy } from 'lucide-react'

const OWNER = 'Belle-Raja Corp'
const AUTHOR = 'Raj Raja'
const CONTACT = 'Contact@Belle-RajaCorp.com'

const CAPABILITIES = [
  'Microsoft 365: Entra ID, Intune, Defender, Purview, Exchange, SharePoint, Teams and Copilot',
  'Amazon Web Services: IAM, S3, CloudTrail, GuardDuty, AWS Config and Security Hub',
  'Google Cloud: IAM, service accounts, firewall rules, audit sinks, buckets, KMS and org policy',
  'Google Workspace: admin roles, 2-step verification, OAuth grants, Drive sharing and devices',
  'Zero Trust assessment across every connected platform, with GRC framework scoring',
]

function Card({ title, children }: Readonly<{ title: string; children: React.ReactNode }>) {
  return (
    <div style={{
      background: 'var(--color-surface)', border: '1px solid var(--color-border)',
      borderRadius: 12, padding: 24,
    }}>
      <h2 style={{ fontSize: 15, fontWeight: 600, margin: '0 0 12px' }}>{title}</h2>
      {children}
    </div>
  )
}

export default function AboutPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 860 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        <img src="/belle-raja-corp.png" alt={`${OWNER} logo`} width={84} height={84} />
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>UniMonitor</h1>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: '4px 0 0' }}>
            Unified multi-cloud security monitoring and GRC platform
          </p>
        </div>
      </div>

      <Card title="Who makes UniMonitor">
        <p style={{ fontSize: 13, margin: '0 0 8px' }}>
          UniMonitor is designed and built by <strong>{AUTHOR}</strong> and is owned and published by{' '}
          <strong>{OWNER}</strong>.
        </p>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: 0 }}>
          For support, licensing or security questions, contact{' '}
          <a href={`mailto:${CONTACT}`} style={{ color: 'var(--color-brand)' }}>{CONTACT}</a>.
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 16 }}>
          <a href={`mailto:${CONTACT}`} style={action}>
            <Mail size={14} /> Email support
          </a>
          <a href="https://github.com/rajtechlead/UniMonitor" target="_blank" rel="noreferrer" style={action}>
            <Globe size={14} /> Project repository
          </a>
        </div>
      </Card>

      <Card title="What it covers">
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.9 }}>
          {CAPABILITIES.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </Card>

      <Card title="Getting help">
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.9 }}>
          <li>Re-run the first-run wizard at <code>/setup</code> to add or reconnect a platform.</li>
          <li>Settings → Platform connections shows each connection&apos;s state and certificate expiry.</li>
          <li>Data Collection shows when each collector last ran and any error it returned.</li>
          <li>Zero Trust → ZT Assessment holds the current scores; the PowerShell runner stays available as a manual, offline option.</li>
        </ul>
        <p style={{ fontSize: 12, color: 'var(--color-text-muted)', margin: '12px 0 0', display: 'flex', gap: 6, alignItems: 'center' }}>
          <LifeBuoy size={13} /> {OWNER}
        </p>
      </Card>

      <Card title="Acknowledgements">
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: 0, display: 'flex', gap: 6 }}>
          <ShieldCheck size={14} style={{ flexShrink: 0, marginTop: 2 }} />
          The Zero Trust check catalogue follows Microsoft&apos;s open-source Zero Trust Assessment
          project; the Microsoft 365 coverage also draws on Vigil365 and m365_sheppard.
        </p>
      </Card>
    </div>
  )
}

const action: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px',
  borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
  color: 'var(--color-text)', fontSize: 13, textDecoration: 'none',
}
