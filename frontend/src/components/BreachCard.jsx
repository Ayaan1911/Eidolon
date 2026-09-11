const severityStyles = {
  High: "bg-red-100 text-red-700",
  Medium: "bg-amber-100 text-amber-700",
}

export default function BreachCard({ breach }) {
  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">{breach.name}</h3>
        <span
          className={`text-xs font-medium px-2 py-1 rounded-full ${
            severityStyles[breach.severity] || "bg-gray-100 text-gray-700"
          }`}
        >
          {breach.severity}
        </span>
      </div>
      <p className="text-sm text-gray-500 mt-1">{breach.date}</p>
      <p className="text-sm text-gray-600 mt-2">
        Exposed: {breach.data_exposed.join(", ")}
      </p>
    </div>
  )
}
