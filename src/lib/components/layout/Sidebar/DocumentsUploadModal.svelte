<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import DocumentArrowUp from '$lib/components/icons/DocumentArrowUp.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import { createDocument, createDocumentsBatch, getDocumentStatus } from '$lib/apis/documents';

	const i18n = getContext('i18n');

	export let show = false;

	type UploadEntry = {
		itemId: string;
		documentId: string | null;
		name: string;
		size: number;
		status: 'uploading' | 'uploaded' | 'failed';
		error?: string;
		collection_name?: string;
		collection_names?: string[];
	};

	const ADD_EVENT = 'open-webui:documents:add';
	const UPDATE_EVENT = 'open-webui:documents:update';

	let singleInput: HTMLInputElement;
	let batchInput: HTMLInputElement;
	let uploads: UploadEntry[] = [];

	const newItemId = () =>
		(typeof crypto !== 'undefined' && crypto.randomUUID
			? crypto.randomUUID()
			: `${Date.now()}-${Math.random().toString(16).slice(2)}`);

	const toDetailFile = (entry: UploadEntry) => ({
		itemId: entry.itemId,
		id: entry.documentId ?? entry.itemId,
		document_id: entry.documentId ?? undefined,
		type: 'doc',
		name: entry.name,
		size: entry.size,
		status: entry.status,
		error: entry.error ?? '',
		collection_name: entry.collection_name,
		collection_names: entry.collection_names
	});

	const emitAdd = (entries: UploadEntry[]) => {
		window.dispatchEvent(
			new CustomEvent(ADD_EVENT, {
				detail: {
					files: entries.map(toDetailFile)
				}
			})
		);
	};

	const emitUpdate = (entry: UploadEntry) => {
		window.dispatchEvent(
			new CustomEvent(UPDATE_EVENT, {
				detail: {
					file: toDetailFile(entry)
				}
			})
		);
	};

	const updateEntry = (itemId: string, patch: Partial<UploadEntry>) => {
		uploads = uploads.map((entry) => (entry.itemId === itemId ? { ...entry, ...patch } : entry));
		const updated = uploads.find((entry) => entry.itemId === itemId);
		if (updated) {
			emitUpdate(updated);
		}
		return updated;
	};

	const extractValue = (obj: any, paths: string[][]) => {
		for (const path of paths) {
			let current = obj;
			let found = true;
			for (const key of path) {
				if (current == null || !(key in current)) {
					found = false;
					break;
				}
				current = current[key];
			}
			if (found && current != null && current !== '') {
				return current;
			}
		}
		return undefined;
	};

	const normalizeStatusPayload = (payload: any, fallbackName: string) => {
		const rawStatus = String(
			extractValue(payload, [
				['status'],
				['state'],
				['processing_status'],
				['indexing_status'],
				['document', 'status'],
				['data', 'status']
			]) ?? ''
		).toLowerCase();

		let status: UploadEntry['status'] = 'uploading';
		if (
			rawStatus.includes('completed') ||
			rawStatus.includes('indexed') ||
			rawStatus.includes('success') ||
			rawStatus.includes('succeeded')
		) {
			status = 'uploaded';
		} else if (rawStatus.includes('fail') || rawStatus.includes('error')) {
			status = 'failed';
		}

		const collectionName = extractValue(payload, [
			['collection_name'],
			['metadata', 'collection_name'],
			['indexed_metadata', 'collection_name'],
			['document', 'collection_name'],
			['data', 'collection_name']
		]);

		const collectionNames =
			extractValue(payload, [
				['collection_names'],
				['metadata', 'collection_names'],
				['indexed_metadata', 'collection_names'],
				['document', 'collection_names'],
				['data', 'collection_names']
			]) ?? undefined;

		const error =
			extractValue(payload, [['error'], ['detail'], ['message'], ['document', 'error']]) ?? undefined;

		return {
			name:
				extractValue(payload, [['name'], ['filename'], ['title'], ['document', 'name']]) ??
				fallbackName,
			status,
			error,
			collection_name: collectionName,
			collection_names: Array.isArray(collectionNames) ? collectionNames : undefined
		};
	};

	const extractDocumentId = (payload: any) =>
		extractValue(payload, [['document_id'], ['id'], ['document', 'id'], ['data', 'id']]);

	const extractBatchItems = (payload: any) => {
		if (Array.isArray(payload)) return payload;
		const documentIds = extractValue(payload, [['document_ids'], ['data', 'document_ids']]);
		if (Array.isArray(documentIds)) {
			return documentIds.map((document_id) => ({ document_id }));
		}
		return (
			extractValue(payload, [['documents'], ['results'], ['items'], ['data', 'documents']]) ?? []
		);
	};

	const pollDocument = async (entry: UploadEntry) => {
		if (!entry.documentId) {
			updateEntry(entry.itemId, {
				status: 'failed',
				error: 'Document ID missing from upload response'
			});
			return;
		}

		for (let attempt = 0; attempt < 180; attempt += 1) {
			try {
				const payload = await getDocumentStatus(localStorage.token, entry.documentId);
				const normalized = normalizeStatusPayload(payload, entry.name);
				const updated = updateEntry(entry.itemId, {
					...normalized,
					documentId: entry.documentId
				});

				if (updated?.status === 'uploaded') {
					return;
				}

				if (updated?.status === 'failed') {
					if (updated.error) {
						toast.error(updated.error);
					}
					return;
				}
			} catch (error) {
				const message = error?.detail || error?.message || `${error}`;
				updateEntry(entry.itemId, {
					status: 'failed',
					error: message
				});
				toast.error(message);
				return;
			}

			await new Promise((resolve) => setTimeout(resolve, 2000));
		}

		updateEntry(entry.itemId, {
			status: 'failed',
			error: 'Timed out while waiting for indexing to complete'
		});
	};

	const startSingleUpload = async (file: File) => {
		const entry: UploadEntry = {
			itemId: newItemId(),
			documentId: null,
			name: file.name,
			size: file.size,
			status: 'uploading'
		};

		uploads = [entry, ...uploads];
		emitAdd([entry]);

		try {
			const payload = await createDocument(localStorage.token, file);
			const documentId = extractDocumentId(payload);
			const updated = updateEntry(entry.itemId, { documentId });
			if (updated) {
				await pollDocument(updated);
			}
		} catch (error) {
			const message = error?.detail || error?.message || `${error}`;
			updateEntry(entry.itemId, {
				status: 'failed',
				error: message
			});
			toast.error(message);
		}
	};

	const startBatchUpload = async (files: File[]) => {
		const pendingEntries = files.map((file) => ({
			itemId: newItemId(),
			documentId: null,
			name: file.name,
			size: file.size,
			status: 'uploading' as const
		}));

		uploads = [...pendingEntries, ...uploads];
		emitAdd(pendingEntries);

		try {
			const payload = await createDocumentsBatch(localStorage.token, files);
			const items = extractBatchItems(payload);

			if (!Array.isArray(items) || items.length === 0) {
				throw new Error('Batch upload response did not include document items');
			}

			await Promise.all(
				pendingEntries.map(async (entry, index) => {
					const responseItem = items[index] ?? {};
					const documentId = extractDocumentId(responseItem);
					const updated = updateEntry(entry.itemId, {
						documentId,
						name:
							extractValue(responseItem, [['name'], ['filename'], ['title']]) ?? entry.name
					});
					if (updated) {
						await pollDocument(updated);
					}
				})
			);
		} catch (error) {
			const message = error?.detail || error?.message || `${error}`;
			for (const entry of pendingEntries) {
				updateEntry(entry.itemId, {
					status: 'failed',
					error: message
				});
			}
			toast.error(message);
		}
	};

	const handleSingleChange = async (event: Event) => {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		input.value = '';
		await startSingleUpload(file);
	};

	const handleBatchChange = async (event: Event) => {
		const input = event.currentTarget as HTMLInputElement;
		const files = input.files ? Array.from(input.files) : [];
		if (files.length === 0) return;
		input.value = '';
		await startBatchUpload(files);
	};
</script>

<Modal bind:show size="lg">
	<div class="p-6 md:p-7">
		<div class="flex items-start justify-between gap-4">
			<div>
				<div class="text-xl font-semibold text-gray-900 dark:text-gray-100">
					{$i18n.t('Documents')}
				</div>
				<div class="mt-1 text-sm text-gray-500">
					{$i18n.t('Upload files and wait for indexing before sending your next message.')}
				</div>
			</div>

			<button
				type="button"
				class="rounded-full p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:hover:bg-gray-800 dark:hover:text-gray-100"
				on:click={() => {
					show = false;
				}}
			>
				<XMark className="size-5" />
			</button>
		</div>

		<div class="mt-6 rounded-3xl border border-dashed border-gray-300 bg-gray-50/60 p-6 dark:border-gray-700 dark:bg-gray-900/40">
			<div class="flex flex-col items-center text-center">
				<div class="rounded-2xl bg-white p-3 text-gray-700 shadow-sm dark:bg-gray-800 dark:text-gray-100">
					<DocumentArrowUp className="size-8" strokeWidth="1.75" />
				</div>
				<div class="mt-4 text-2xl font-medium text-gray-900 dark:text-gray-100">
					{$i18n.t('Upload documents')}
				</div>
				<div class="mt-2 max-w-xl text-sm text-gray-500">
					{$i18n.t('Single upload uses the one-file endpoint. Batch upload sends multiple files to the batch endpoint.')}
				</div>

				<div class="mt-6 flex flex-wrap items-center justify-center gap-3">
					<button
						type="button"
						class="rounded-2xl border border-gray-200 bg-white px-4 py-2.5 text-sm font-medium text-gray-900 hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-850 dark:text-gray-100 dark:hover:bg-gray-800"
						on:click={() => singleInput?.click()}
					>
						{$i18n.t('Upload Single File')}
					</button>

					<button
						type="button"
						class="rounded-2xl border border-gray-200 bg-white px-4 py-2.5 text-sm font-medium text-gray-900 hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-850 dark:text-gray-100 dark:hover:bg-gray-800"
						on:click={() => batchInput?.click()}
					>
						{$i18n.t('Upload Multiple Files')}
					</button>
				</div>

				<input
					bind:this={singleInput}
					type="file"
					accept=".pdf,.md,text/markdown,application/pdf"
					class="hidden"
					on:change={handleSingleChange}
				/>

				<input
					bind:this={batchInput}
					type="file"
					multiple
					accept=".pdf,.md,text/markdown,application/pdf"
					class="hidden"
					on:change={handleBatchChange}
				/>
			</div>
		</div>

		<div class="mt-6">
			<div class="text-sm font-medium text-gray-900 dark:text-gray-100">
				{$i18n.t('Indexing status')}
			</div>

			{#if uploads.length === 0}
				<div class="mt-3 rounded-2xl border border-gray-200 px-4 py-3 text-sm text-gray-500 dark:border-gray-800">
					{$i18n.t('No documents uploaded yet.')}
				</div>
			{:else}
				<div class="mt-3 space-y-2">
					{#each uploads as upload (upload.itemId)}
						<div class="flex items-center justify-between gap-3 rounded-2xl border border-gray-200 px-4 py-3 dark:border-gray-800">
							<div class="min-w-0">
								<div class="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
									{upload.name}
								</div>
								<div class="mt-1 text-xs text-gray-500">
									{#if upload.status === 'uploading'}
										{$i18n.t('Indexing in progress')}
									{:else if upload.status === 'uploaded'}
										{$i18n.t('Indexed and ready')}
									{:else}
										{upload.error || $i18n.t('Indexing failed')}
									{/if}
								</div>
							</div>

							<div class="shrink-0">
								{#if upload.status === 'uploading'}
									<div class="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400">
										<Spinner className="size-4" />
										<span>{$i18n.t('Processing')}</span>
									</div>
								{:else if upload.status === 'uploaded'}
									<div class="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
										{$i18n.t('Ready')}
									</div>
								{:else}
									<div class="rounded-full bg-red-100 px-2.5 py-1 text-xs font-medium text-red-700 dark:bg-red-500/15 dark:text-red-300">
										{$i18n.t('Failed')}
									</div>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</Modal>
