import BreachCard from "../components/BreachCard"

function riskColor(score) {
  if (score >= 70) return "text-red-600"
  if (score >= 30) return "text-amber-600"
  return "text-green-600"
}

export default function ExposureReport({ result, onReset }) {
  const { email, risk_score, total_breaches, breaches } = result

  return (
    <div className="min-h-screen px-4 py-10">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Exposure report</h1>
            <p className="text-gray-500">{email}</p>
          </div>
          <button
            onClick={onReset}
            className="text-sm text-gray-500 hover:text-gray-900"
          >
            Check another
          </button>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="border border-gray-200 rounded-lg p-4">
            <p className="text-sm text-gray-500">Risk score</p>
            <p className={`text-3xl font-bold ${riskColor(risk_score)}`}>
              {risk_score}
            </p>
          </div>
          <div className="border border-gray-200 rounded-lg p-4">
            <p className="text-sm text-gray-500">Breaches found</p>
            <p className="text-3xl font-bold text-gray-900">{total_breaches}</p>
          </div>
        </div>

        {total_breaches === 0 ? (
          <p className="text-gray-600">No known breaches for this address.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {breaches.map((breach) => (
              <BreachCard key={breach.name} breach={breach} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
