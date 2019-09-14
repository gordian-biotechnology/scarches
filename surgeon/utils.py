import numpy as np
import scanpy as sc
from scipy import sparse
from sklearn.preprocessing import LabelEncoder


def label_encoder(adata, label_encoder, condition_key='condition'):
    """
        Encode labels of Annotated `adata` matrix using sklearn.preprocessing.LabelEncoder class.
        Parameters
        ----------
        adata: `~anndata.AnnData`
            Annotated data matrix.
        Returns
        -------
        labels: numpy nd-array
            Array of encoded labels
        Example
        --------
        >>> import surgeon
        >>> import scanpy as sc
        >>> train_data = sc.read("./data/train.h5ad")
        >>> train_labels, label_encoder = surgeon.utils.label_encoder(train_data)
    """
    labels = np.zeros(adata.shape[0])
    if isinstance(label_encoder, dict):
        for condition, label in label_encoder.items():
            labels[adata.obs[condition_key] == condition] = label
    elif isinstance(label_encoder, LabelEncoder):
        labels = label_encoder.transform(adata.obs[condition_key].values)
    else:
        label_encoder = LabelEncoder()
        labels = label_encoder.fit_transform(adata.obs[condition_key].values)
    return labels.reshape(-1, 1), label_encoder


def remove_sparsity(adata):
    if sparse.issparse(adata.X):
        adata.X = adata.X.A

    return adata


def train_test_split(adata, train_frac=0.85):
    train_size = int(adata.shape[0] * train_frac)
    indices = np.arange(adata.shape[0])
    np.random.shuffle(indices)
    train_idx = indices[:train_size]
    test_idx = indices[train_size:]

    train_data = adata[train_idx, :]
    valid_data = adata[test_idx, :]

    return train_data, valid_data


def normalize(adata, batch_key=None, filter_min_counts=True, size_factors=True, logtrans_input=True,
              target_sum=None, n_top_genes=2000):
    if filter_min_counts:
        sc.pp.filter_genes(adata, min_counts=1)
        sc.pp.filter_cells(adata, min_counts=1)

    adata_count = adata.copy()

    if size_factors:
        sc.pp.normalize_total(adata, target_sum=target_sum, exclude_highly_expressed=True, key_added='size_factors')
        # adata.obs['size_factors'] = adata.obs.n_counts / np.median(adata.obs.n_counts)
    else:
        adata.obs['size_factors'] = 1.0

    if logtrans_input:
        sc.pp.log1p(adata)

    if n_top_genes > 0 and adata.shape[1] > n_top_genes:
        genes = hvg_batch(adata.copy(), batch_key=batch_key, adataOut=False, target_genes=n_top_genes)
        # sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes, batch_key=batch_key)
        # genes = adata.var['highly_variable']
        adata = adata[:, genes]
        adata_count = adata_count[:, genes]

    if sparse.issparse(adata_count.X):
        adata_count.X = adata_count.X.A

    if sparse.issparse(adata.X):
        adata.X = adata.X.A

    if size_factors or logtrans_input:
        adata.raw = adata_count.copy()
    else:
        adata.raw = adata_count

    return adata


def create_dictionary(conditions, target_conditions):
    if not isinstance(target_conditions, list):
        target_conditions = [target_conditions]

    dictionary = {}
    conditions = [e for e in conditions if e not in target_conditions]
    for idx, condition in enumerate(conditions):
        dictionary[condition] = idx
    return dictionary


def hvg_batch(adata, batch_key=None, target_genes=2000, flavor='cell_ranger', n_bins=20, adataOut=False):
    """
    Method to select HVGs based on mean dispersions of genes that are highly
    variable genes in all batches. Using a the top target_genes per batch by
    average normalize dispersion. If target genes still hasn't been reached,
    then HVGs in all but one batches are used to fill up. This is continued
    until HVGs in a single batch are considered.
    """

    adata_hvg = adata if adataOut else adata.copy()

    n_batches = len(adata_hvg.obs[batch_key].cat.categories)

    # Calculate double target genes per dataset
    sc.pp.highly_variable_genes(adata_hvg,
                                flavor=flavor,
                                n_top_genes=target_genes,
                                n_bins=n_bins,
                                batch_key=batch_key,
                                )

    nbatch1_dispersions = adata_hvg.var['dispersions_norm'][adata_hvg.var.highly_variable_nbatches >
                                                            len(adata_hvg.obs[batch_key].cat.categories) - 1]

    nbatch1_dispersions.sort_values(ascending=False, inplace=True)

    if len(nbatch1_dispersions) > target_genes:
        hvg = nbatch1_dispersions.index[:target_genes]

    else:
        enough = False
        print(f'Using {len(nbatch1_dispersions)} HVGs from full intersect set')
        hvg = nbatch1_dispersions.index[:]
        not_n_batches = 1

        while not enough:
            target_genes_diff = target_genes - len(hvg)

            tmp_dispersions = adata_hvg.var['dispersions_norm'][adata_hvg.var.highly_variable_nbatches ==
                                                                (n_batches - not_n_batches)]

            if len(tmp_dispersions) < target_genes_diff:
                print(f'Using {len(tmp_dispersions)} HVGs from n_batch-{not_n_batches} set')
                hvg = hvg.append(tmp_dispersions.index)
                not_n_batches += 1

            else:
                print(f'Using {target_genes_diff} HVGs from n_batch-{not_n_batches} set')
                tmp_dispersions.sort_values(ascending=False, inplace=True)
                hvg = hvg.append(tmp_dispersions.index[:target_genes_diff])
                enough = True

    print(f'Using {len(hvg)} HVGs')

    if not adataOut:
        del adata_hvg
        return hvg.tolist()
    else:
        return adata_hvg[:, hvg].copy()

