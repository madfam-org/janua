export default function AdminPage() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">Plinto Internal Admin</h1>
        <p className="text-muted-foreground mb-8">Superadmin tools for platform management</p>
        <div className="bg-card p-6 rounded-lg border">
          <p className="text-sm text-muted-foreground">
            This is the internal admin dashboard for Plinto team members only.
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Access restricted to authorized personnel.
          </p>
        </div>
      </div>
    </div>
  )
}