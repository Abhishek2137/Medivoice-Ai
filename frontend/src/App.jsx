import { useEffect, useState } from "react";
import PatientHome, { DoctorsDirectory } from "./pages/PatientHome";
import DoctorDashboard from "./pages/DoctorDashboard";
import DoctorProfile from "./pages/DoctorProfile";
import {
	getCurrentDoctor,
	getCurrentPatient,
	loginDoctor,
	loginPatient,
	registerPatient,
} from "./services/api";

function AuthPage({ onAuthenticated, doctorPortal = false }) {
	const [isRegistering, setIsRegistering] = useState(false);
	const [name, setName] = useState("");
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [error, setError] = useState("");
	const [isSubmitting, setIsSubmitting] = useState(false);

	async function submit(event) {
		event.preventDefault();
		setError("");
		setIsSubmitting(true);
		try {
			const result = doctorPortal
				? await loginDoctor({ email, password })
				: isRegistering
					? await registerPatient({ name, email, password })
					: await loginPatient({ email, password });
			onAuthenticated(result);
		} catch (requestError) {
			setError(requestError.message);
		} finally {
			setIsSubmitting(false);
		}
	}

	return (
		<div className="app-shell">
			<header className="topbar">
				<a className="brand" href="/" aria-label="MediVoice home">
					<span className="brand-mark">+</span><span>MediVoice <em>AI</em></span>
				</a>
			</header>
			<main className="page-content auth-page">
				<div className="auth-grid">
					<section className="hero-copy">
						<div className="eyebrow">Your calm path to care</div>
						<h1>{doctorPortal ? "Your clinic, in control." : isRegistering ? "Create your patient account." : "Welcome back."}</h1>
						<p>{doctorPortal ? "Sign in to securely review appointment requests addressed to you." : "Sign in to securely manage your appointments, or browse doctors without an account."}</p>
					</section>
					<form className="auth-card" id="auth-card" onSubmit={submit}>
					<div className="eyebrow">{doctorPortal ? "Doctor login" : isRegistering ? "Patient registration" : "Patient login"}</div>
					<h2>{doctorPortal ? "Doctor dashboard" : isRegistering ? "Start with your details" : "Sign in to MediVoice"}</h2>
					{isRegistering && !doctorPortal && (
						<label>Full name<input autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} required maxLength={120} /></label>
					)}
					<label>Email address<input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required maxLength={320} /></label>
					<label>Password<input type="password" autoComplete={isRegistering ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} required minLength={isRegistering ? 10 : 1} maxLength={128} /></label>
					{isRegistering && !doctorPortal && <p className="form-hint">Use at least 10 characters.</p>}
					{error && <p className="inline-error" role="alert">{error}</p>}
					<button className="primary-button full-width" type="submit" disabled={isSubmitting}>
						{isSubmitting ? "Please wait..." : isRegistering && !doctorPortal ? "Create account" : "Sign in"}
					</button>
					{!doctorPortal && <button className="text-button" type="button" onClick={() => { setError(""); setIsRegistering((value) => !value); }}>
						{isRegistering ? "Already registered? Sign in" : "New here? Create a patient account"}
					</button>}
					<a className="text-button" href={doctorPortal ? "/" : "/doctor"}>{doctorPortal ? "Patient sign in" : "Doctor sign in"}</a>
					</form>
				</div>
				{!doctorPortal && <DoctorsDirectory
					publicOnly
					onSignIn={() => document.getElementById("auth-card")?.scrollIntoView({ behavior: "smooth" })}
				/>}
			</main>
		</div>
	);
}

export default function App() {
	const doctorPortal = window.location.pathname.startsWith("/doctor");
	const doctorProfile = window.location.pathname.match(/^\/doctors\/(\d+)\/?$/);
	const [account, setAccount] = useState(null);
	const [isLoading, setIsLoading] = useState(true);

	useEffect(() => {
		const tokenKey = doctorPortal ? "medivoice-doctor-token" : "medivoice-token";
		if (!window.sessionStorage.getItem(tokenKey)) {
			setIsLoading(false);
			return;
		}
		(doctorPortal ? getCurrentDoctor() : getCurrentPatient())
			.then(setAccount)
			.catch(() => {
				window.sessionStorage.removeItem(tokenKey);
				setAccount(null);
			})
			.finally(() => setIsLoading(false));
	}, [doctorPortal]);

	function handleAuthenticated(result) {
		const tokenKey = doctorPortal ? "medivoice-doctor-token" : "medivoice-token";
		window.sessionStorage.setItem(tokenKey, result.access_token);
		setAccount(doctorPortal ? result.doctor : result.patient);
	}

	function logout() {
		const tokenKey = doctorPortal ? "medivoice-doctor-token" : "medivoice-token";
		window.sessionStorage.removeItem(tokenKey);
		setAccount(null);
	}

	if (isLoading) return <main className="auth-loading">Loading your secure session...</main>;
	if (doctorProfile) return <DoctorProfile doctorId={Number(doctorProfile[1])} patient={account} />;
	if (!account) return <AuthPage onAuthenticated={handleAuthenticated} doctorPortal={doctorPortal} />;
	if (doctorPortal) return <DoctorDashboard doctor={account} onLogout={logout} />;
	return <PatientHome patient={account} onLogout={logout} />;
}
