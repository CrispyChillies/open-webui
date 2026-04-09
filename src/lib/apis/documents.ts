import { WEBUI_API_BASE_URL } from '$lib/constants';

const parseJsonResponse = async (res: Response) => {
	if (!res.ok) {
		let error: any = null;
		try {
			error = await res.json();
		} catch {
			error = { detail: await res.text() };
		}
		throw error;
	}

	return res.json();
};

export const createDocument = async (token: string, file: File) => {
	const data = new FormData();
	data.append('file', file);

	return fetch(`${WEBUI_API_BASE_URL}/documents`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			authorization: `Bearer ${token}`
		},
		body: data
	}).then(parseJsonResponse);
};

export const createDocumentsBatch = async (token: string, files: File[]) => {
	const data = new FormData();
	for (const file of files) {
		data.append('files', file);
	}

	return fetch(`${WEBUI_API_BASE_URL}/documents/batch`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			authorization: `Bearer ${token}`
		},
		body: data
	}).then(parseJsonResponse);
};

export const getDocumentStatus = async (token: string, documentId: string) => {
	return fetch(`${WEBUI_API_BASE_URL}/documents/${documentId}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	}).then(parseJsonResponse);
};
