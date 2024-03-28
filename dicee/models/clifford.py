from .base_model import BaseKGE
import torch
from torch.nn import functional as F
from torch import nn


class CMult(BaseKGE):
    """
    The CMult class represents a specific kind of mathematical object used in knowledge graph embeddings,
    involving Clifford algebra multiplication. It defines several algebraic structures based on the signature (p, q),
    such as Real Numbers, Complex Numbers, Quaternions, and others. The class provides functionality for
    performing Clifford multiplication, a generalization of the geometric product for vectors in a Clifford algebra.
    
    TODO: Add mathematical format for sphinx.

    Cl_(0,0) => Real Numbers


    Cl_(0,1) =>
                A multivector \mathbf{a} = a_0 + a_1 e_1
                A multivector \mathbf{b} = b_0 + b_1 e_1

                multiplication is isomorphic to the product of two complex numbers

                \mathbf{a} \times \mathbf{b} = a_0 b_0 + a_0b_1 e1 + a_1 b_1 e_1 e_1
                                             = (a_0 b_0 - a_1 b_1) + (a_0 b_1 + a_1 b_0) e_1
    Cl_(2,0) =>
                A multivector \mathbf{a} = a_0 + a_1 e_1 + a_2 e_2 + a_{12} e_1 e_2
                A multivector \mathbf{b} = b_0 + b_1 e_1 + b_2 e_2 + b_{12} e_1 e_2

                \mathbf{a} \times \mathbf{b} = a_0b_0 + a_0b_1 e_1 + a_0b_2e_2 + a_0 b_12 e_1 e_2
                                            + a_1 b_0 e_1 + a_1b_1 e_1_e1 ..

    Cl_(0,2) => Quaternions

    Attributes
    ----------
    name : str
        The name identifier for the CMult class.
    entity_embeddings : torch.nn.Embedding
        Embedding layer for entities in the knowledge graph.
    relation_embeddings : torch.nn.Embedding
        Embedding layer for relations in the knowledge graph.
    p : int
        Non-negative integer representing the number of positive square terms in the Clifford algebra.
    q : int
        Non-negative integer representing the number of negative square terms in the Clifford algebra.

    Methods
    -------
    clifford_mul(x: torch.FloatTensor, y: torch.FloatTensor, p: int, q: int) -> tuple
        Performs Clifford multiplication based on the given signature (p, q).
    score(head_ent_emb, rel_ent_emb, tail_ent_emb) -> torch.FloatTensor
        Computes a scoring function for a head entity, relation, and tail entity embeddings.
    forward_triples(x: torch.LongTensor) -> torch.FloatTensor
        Computes scores for a batch of triples.
    forward_k_vs_all(x: torch.Tensor) -> torch.FloatTensor
        Computes scores for a batch of triples against all entities in the knowledge graph.
    """

    def __init__(self, args):
        super().__init__(args)
        self.name = "CMult"
        self.entity_embeddings = torch.nn.Embedding(
            self.num_entities, self.embedding_dim
        )
        self.relation_embeddings = torch.nn.Embedding(
            self.num_relations, self.embedding_dim
        )
        self.param_init(self.entity_embeddings.weight.data), self.param_init(
            self.relation_embeddings.weight.data
        )
        self.p = self.args["p"]
        self.q = self.args["q"]
        if self.p is None:
            self.p = 0
        if self.q is None:
            self.q = 0
        print(f"\tp:{self.p}\tq:{self.q}")

    def clifford_mul(
        self, x: torch.FloatTensor, y: torch.FloatTensor, p: int, q: int
    ) -> tuple:
        """
        Performs Clifford multiplication in the Clifford algebra Cl_{p,q}. This method generalizes the geometric product
        of vectors in a Clifford algebra, handling different algebraic structures like real numbers, complex numbers,
        quaternions, etc., based on the signature (p, q).

        Clifford multiplication Cl_{p,q} (\mathbb{R})

        ei ^2 = +1     for i =< i =< p
        ej ^2 = -1     for p < j =< p+q
        ei ej = -eje1  for i \neq j

        Parameters
        ----------
        x : torch.FloatTensor
            The first multivector operand with shape (n, d).
        y : torch.FloatTensor
            The second multivector operand with shape (n, d).
        p : int
            A non-negative integer representing the number of positive square terms in the Clifford algebra.
        q : int
            A non-negative integer representing the number of negative square terms in the Clifford algebra.

        Returns
        -------
        tuple
            The result of Clifford multiplication, a tuple of tensors representing the components of the resulting multivector.
        """

        if p == q == 0:
            return x * y
        elif (p == 1 and q == 0) or (p == 0 and q == 1):
            # {1,e1} e_i^2 = +1 for i
            a0, a1 = torch.hsplit(x, 2)
            b0, b1 = torch.hsplit(y, 2)
            if p == 1 and q == 0:
                ab0 = a0 * b0 + a1 * b1
                ab1 = a0 * b1 + a1 * b0
            else:
                ab0 = a0 * b0 - a1 * b1
                ab1 = a0 * b1 + a1 * b0
            return ab0, ab1
        elif (p == 2 and q == 0) or (p == 0 and q == 2):
            a0, a1, a2, a12 = torch.hsplit(x, 4)
            b0, b1, b2, b12 = torch.hsplit(y, 4)
            if p == 2 and q == 0:
                ab0 = a0 * b0 + a1 * b1 + a2 * b2 - a12 * b12
                ab1 = a0 * b1 + a1 * b0 - a2 * b12 + a12 * b2
                ab2 = a0 * b2 + a1 * b12 + a2 * b0 - a12 * b1
                ab12 = a0 * b12 + a1 * b2 - a2 * b1 + a12 * b0
            else:
                ab0 = a0 * b0 - a1 * b1 - a2 * b2 - a12 * b12
                ab1 = a0 * b1 + a1 * b0 + a2 * b12 - a12 * b2
                ab2 = a0 * b2 - a1 * b12 + a2 * b0 + a12 * b1
                ab12 = a0 * b12 + a1 * b2 - a2 * b1 + a12 * b0
            return ab0, ab1, ab2, ab12
        elif p == 1 and q == 1:
            a0, a1, a2, a12 = torch.hsplit(x, 4)
            b0, b1, b2, b12 = torch.hsplit(y, 4)

            ab0 = a0 * b0 + a1 * b1 - a2 * b2 + a12 * b12
            ab1 = a0 * b1 + a1 * b0 + a2 * b12 - a12 * b2
            ab2 = a0 * b2 + a1 * b12 + a2 * b0 - a12 * b1
            ab12 = a0 * b12 + a1 * b2 - a2 * b1 + a12 * b0
            return ab0, ab1, ab2, ab12
        elif p == 3 and q == 0:
            # cl3,0 no 0,3
            a0, a1, a2, a3, a12, a13, a23, a123 = torch.hsplit(x, 8)
            b0, b1, b2, b3, b12, b13, b23, b123 = torch.hsplit(y, 8)

            ab0 = (
                a0 * b0
                + a1 * b1
                + a2 * b2
                + a3 * b3
                - a12 * b12
                - a13 * b13
                - a23 * b23
                - a123 * b123
            )
            ab1 = (
                a0 * b1
                + a1 * b0
                - a2 * b12
                - a3 * b13
                + a12 * b2
                + a13 * b3
                - a23 * b123
                - a123 * b23
            )
            ab2 = (
                a0 * b2
                + a1 * b12
                + a2 * b0
                - a3 * b23
                - a12 * b1
                + a13 * b123
                + a23 * b3
                + a123 * b13
            )
            ab3 = (
                a0 * b3
                + a1 * b13
                + a2 * b23
                + a3 * b0
                - a12 * b123
                - a13 * b1
                - a23 * b2
                - a123 * b12
            )
            ab12 = (
                a0 * b12
                + a1 * b2
                - a2 * b1
                + a3 * b123
                + a12 * b0
                - a13 * b23
                + a23 * b13
                + a123 * b3
            )
            ab13 = (
                a0 * b13
                + a1 * b3
                - a2 * b123
                - a3 * b1
                + a12 * b23
                + a13 * b0
                - a23 * b12
                - a123 * b2
            )
            ab23 = (
                a0 * b23
                + a1 * b123
                + a2 * b3
                - a3 * b2
                - a12 * b13
                - a13 * b12
                + a23 * b0
                + a123 * b1
            )
            ab123 = (
                a0 * b123
                + a1 * b23
                - a2 * b13
                + a3 * b12
                + a12 * b3
                - a13 * b2
                + a23 * b1
                + a123 * b0
            )
            return ab0, ab1, ab2, ab3, ab12, ab13, ab23, ab123
        else:
            raise NotImplementedError

    def score(
        self,
        head_ent_emb: torch.FloatTensor,
        rel_ent_emb: torch.FloatTensor,
        tail_ent_emb: torch.FloatTensor,
    ) -> torch.FloatTensor:
        """
        Computes a scoring function for a given triple of head entity, relation, and tail entity embeddings.
        The method involves Clifford multiplication of the head entity and relation embeddings, followed by
        a calculation of the score with the tail entity embedding.

        Parameters
        ----------
        head_ent_emb : torch.FloatTensor
            Embedding of the head entity.
        rel_ent_emb : torch.FloatTensor
            Embedding of the relation.
        tail_ent_emb : torch.FloatTensor
            Embedding of the tail entity.

        Returns
        -------
        torch.FloatTensor
            A tensor representing the score of the given triple.
        """
        ab = self.clifford_mul(x=head_ent_emb, y=rel_ent_emb, p=self.p, q=self.q)

        if self.p == self.q == 0:
            return torch.einsum("bd,bd->b", ab, tail_ent_emb)
        elif (self.p == 1 and self.q == 0) or (self.p == 0 and self.q == 1):
            ab0, ab1 = ab
            c0, c1 = torch.hsplit(tail_ent_emb, 2)
            return torch.einsum("bd,bd->b", ab0, c0) + torch.einsum("bd,bd->b", ab1, c1)
        elif (self.p == 2 and self.q == 0) or (self.p == 0 and self.q == 2):
            ab0, ab1, ab2, ab12 = ab
            c0, c1, c2, c12 = torch.hsplit(tail_ent_emb, 4)
            return (
                torch.einsum("bd,bd->b", ab0, c0)
                + torch.einsum("bd,bd->b", ab1, c1)
                + torch.einsum("bd,bd->b", ab2, c2)
                + torch.einsum("bd,bd->b", ab12, c12)
            )
        else:
            raise NotImplementedError

    def forward_triples(self, x: torch.LongTensor) -> torch.FloatTensor:
        """
        Computes scores for a batch of triples. This method is typically used in training or evaluation
        of knowledge graph embedding models. It applies Clifford multiplication to the embeddings of head
        entities and relations and then calculates the score with respect to the tail entity embeddings.

        Parameters
        ----------
        x : torch.LongTensor
            A tensor with shape (n, 3) representing a batch of triples, where each triple consists of indices
            for a head entity, a relation, and a tail entity.

        Returns
        -------
        torch.FloatTensor
            A tensor with shape (n,) containing the scores for each triple in the batch.
        """

        # (1) Retrieve real-valued embedding vectors.
        head_ent_emb, rel_ent_emb, tail_ent_emb = self.get_triple_representation(x)
        ab = self.clifford_mul(x=head_ent_emb, y=rel_ent_emb, p=self.p, q=self.q)

        if self.p == self.q == 0:
            return torch.einsum("bd,bd->b", ab, tail_ent_emb)
        elif (self.p == 1 and self.q == 0) or (self.p == 0 and self.q == 1):
            ab0, ab1 = ab
            c0, c1 = torch.hsplit(tail_ent_emb, 2)
            return torch.einsum("bd,bd->b", ab0, c0) + torch.einsum("bd,bd->b", ab1, c1)
        elif (self.p == 2 and self.q == 0) or (self.p == 0 and self.q == 2):
            ab0, ab1, ab2, ab12 = ab
            c0, c1, c2, c12 = torch.hsplit(tail_ent_emb, 4)
            return (
                torch.einsum("bd,bd->b", ab0, c0)
                + torch.einsum("bd,bd->b", ab1, c1)
                + torch.einsum("bd,bd->b", ab2, c2)
                + torch.einsum("bd,bd->b", ab12, c12)
            )
        else:
            raise NotImplementedError

    def forward_k_vs_all(self, x: torch.Tensor) -> torch.FloatTensor:
        """
        Computes scores for a batch of triples against all entities in the knowledge graph, often used in KvsAll evaluation.
        This method retrieves embeddings for heads and relations, performs Clifford multiplication, and then computes the
        inner product with all entity embeddings to get scores for every possible triple involving the given heads and relations.

        Parameters
        ----------
        x : torch.Tensor
            A tensor with shape (n, 3) representing a batch of triples, where each triple consists of indices
            for a head entity and a relation. The tail entity is to be compared against all possible entities.

        Returns
        -------
        torch.FloatTensor
            A tensor with shape (n,) containing scores for each triple against all possible tail entities.
        """
        # (1) Retrieve embedding vectors of heads and relations.
        head_ent_emb, rel_ent_emb = self.get_head_relation_representation(x)
        # (2) CL multiply (1).
        ab = self.clifford_mul(x=head_ent_emb, y=rel_ent_emb, p=self.p, q=self.q)
        # (3) Inner product of (2) and all entity embeddings.
        if self.p == self.q == 0:
            return torch.mm(ab, self.entity_embeddings.weight.transpose(1, 0))
        elif (self.p == 1 and self.q == 0) or (self.p == 0 and self.q == 1):
            ab0, ab1 = ab
            c0, c1 = torch.hsplit(self.entity_embeddings.weight, 2)
            return torch.mm(ab0, c0.transpose(1, 0)) + torch.mm(ab1, c1.transpose(1, 0))
        elif (self.p == 2 and self.q == 0) or (self.p == 0 and self.q == 2):
            ab0, ab1, ab2, ab12 = ab
            c0, c1, c2, c12 = torch.hsplit(self.entity_embeddings.weight, 4)
            return (
                torch.mm(ab0, c0.transpose(1, 0))
                + torch.mm(ab1, c1.transpose(1, 0))
                + torch.mm(ab2, c2.transpose(1, 0))
                + torch.mm(ab12, c12.transpose(1, 0))
            )
        elif self.p == 3 and self.q == 0:
            ab0, ab1, ab2, ab3, ab12, ab13, ab23, ab123 = ab
            c0, c1, c2, c3, c12, c13, c23, c123 = torch.hsplit(
                self.entity_embeddings.weight, 8
            )

            return (
                torch.mm(ab0, c0.transpose(1, 0))
                + torch.mm(ab1, c1.transpose(1, 0))
                + torch.mm(ab2, c2.transpose(1, 0))
                + torch.mm(ab3, c3.transpose(1, 0))
                + torch.mm(ab12, c3.transpose(1, 0))
                + torch.mm(ab13, c13.transpose(1, 0))
                + torch.mm(ab23, c23.transpose(1, 0))
                + torch.mm(ab123, c123.transpose(1, 0))
            )
        elif self.p == 1 and self.q == 1:
            ab0, ab1, ab2, ab12 = ab
            c0, c1, c2, c12 = torch.hsplit(self.entity_embeddings.weight, 4)
            return (
                torch.mm(ab0, c0.transpose(1, 0))
                + torch.mm(ab1, c1.transpose(1, 0))
                + torch.mm(ab2, c2.transpose(1, 0))
                + torch.mm(ab12, c12.transpose(1, 0))
            )

        else:
            raise NotImplementedError


class Keci(BaseKGE):
    """
    The Keci class is a knowledge graph embedding model that incorporates Clifford algebra for embeddings.
    It supports different dimensions of Clifford algebra by setting the parameters p and q. The class
    utilizes Clifford multiplication for embedding interactions and computes scores for knowledge graph triples.

    Parameters
    ----------
    args : dict
        A dictionary of arguments containing hyperparameters and settings for the model.

    Attributes
    ----------
    name : str
        The name identifier for the Keci class.
    p : int
        The parameter 'p' in Clifford algebra, representing the number of positive square terms.
    q : int
        The parameter 'q' in Clifford algebra, representing the number of negative square terms.
    r : int
        A derived attribute for dimension scaling based on 'p' and 'q'.
    p_coefficients : torch.nn.Embedding (optional)
        Embedding for scaling coefficients of 'p' terms, if 'p' > 0.
    q_coefficients : torch.nn.Embedding (optional)
        Embedding for scaling coefficients of 'q' terms, if 'q' > 0.

    Methods
    -------
    compute_sigma_pp(hp: torch.Tensor, rp: torch.Tensor) -> torch.Tensor
        Computes the sigma_pp component in Clifford multiplication.
    compute_sigma_qq(hq: torch.Tensor, rq: torch.Tensor) -> torch.Tensor
        Computes the sigma_qq component in Clifford multiplication.
    compute_sigma_pq(hp: torch.Tensor, hq: torch.Tensor, rp: torch.Tensor, rq: torch.Tensor) -> torch.Tensor
        Computes the sigma_pq component in Clifford multiplication.
    apply_coefficients(h0: torch.Tensor, hp: torch.Tensor, hq: torch.Tensor, r0: torch.Tensor, rp: torch.Tensor, rq: torch.Tensor) -> tuple
        Applies scaling coefficients to the base vectors in Clifford algebra.
    clifford_multiplication(h0: torch.Tensor, hp: torch.Tensor, hq: torch.Tensor, r0: torch.Tensor, rp: torch.Tensor, rq: torch.Tensor) -> tuple
        Performs Clifford multiplication of head and relation embeddings.
    construct_cl_multivector(x: torch.FloatTensor, r: int, p: int, q: int) -> tuple
        Constructs a multivector in Clifford algebra Cl_{p,q}(\mathbb{R}^d).
    forward_k_vs_with_explicit(x: torch.Tensor) -> torch.FloatTensor
        Computes scores for a batch of triples against all entities using explicit Clifford multiplication.
    k_vs_all_score(bpe_head_ent_emb: torch.Tensor, bpe_rel_ent_emb: torch.Tensor, E: torch.Tensor) -> torch.FloatTensor
        Computes scores for all triples using Clifford multiplication in a K-vs-All setup.
    forward_k_vs_all(x: torch.Tensor) -> torch.FloatTensor
        Wrapper function for K-vs-All scoring.
    forward_k_vs_sample(x: torch.LongTensor, target_entity_idx: torch.LongTensor) -> torch.FloatTensor
        Computes scores for a sampled subset of entities.
    score(h: torch.Tensor, r: torch.Tensor, t: torch.Tensor) -> torch.FloatTensor
        Computes the score for a given triple using Clifford multiplication.
    forward_triples(x: torch.Tensor) -> torch.FloatTensor
        Computes scores for a batch of triples.

    Notes
    -----
    The class is designed to work with embeddings in the context of knowledge graph completion tasks,
    leveraging the properties of Clifford algebra for embedding interactions.
    """

    def __init__(self, args: dict):
        super().__init__(args)
        self.name = "Keci"
        self.p = self.args.get("p", 0)
        self.q = self.args.get("q", 0)
        if self.p is None:
            self.p = 0
        if self.q is None:
            self.q = 0
        self.r = self.embedding_dim / (self.p + self.q + 1)
        try:
            assert self.r.is_integer()
        except AssertionError:
            raise AssertionError(
                f"r = embedding_dim / (p + q+ 1) must be a whole number\n"
                f"Currently {self.r}={self.embedding_dim} / ({self.p}+ {self.q} +1)"
            )
        self.r = int(self.r)
        self.requires_grad_for_interactions = True
        # Initialize parameters for dimension scaling
        if self.p > 0:
            self.p_coefficients = torch.nn.Embedding(
                num_embeddings=1, embedding_dim=self.p
            )
            torch.nn.init.zeros_(self.p_coefficients.weight)
        if self.q > 0:
            self.q_coefficients = torch.nn.Embedding(
                num_embeddings=1, embedding_dim=self.q
            )
            torch.nn.init.zeros_(self.q_coefficients.weight)

    def compute_sigma_pp(self, hp: torch.Tensor, rp: torch.Tensor) -> torch.Tensor:
        """
        Computes the sigma_pp component in Clifford multiplication, representing the interactions
        between the positive square terms in the Clifford algebra.

        sigma_{pp} = \sum_{i=1}^{p-1} \sum_{k=i+1}^p (h_i r_k - h_k r_i) e_i e_k, TODO: Add mathematical format for sphinx.

        sigma_{pp} captures the interactions between along p bases
        For instance, let p e_1, e_2, e_3, we compute interactions between e_1 e_2, e_1 e_3 , and e_2 e_3
        This can be implemented with a nested two for loops

                        results = []
                        for i in range(p - 1):
                            for k in range(i + 1, p):
                                results.append(hp[:, :, i] * rp[:, :, k] - hp[:, :, k] * rp[:, :, i])
                        sigma_pp = torch.stack(results, dim=2)
                        assert sigma_pp.shape == (b, r, int((p * (p - 1)) / 2))

        Yet, this computation would be quite inefficient. Instead, we compute interactions along all p,
        e.g., e1e1, e1e2, e1e3,
              e2e1, e2e2, e2e3,
              e3e1, e3e2, e3e3
        Then select the triangular matrix without diagonals: e1e2, e1e3, e2e3.

        Parameters
        ----------
        hp : torch.Tensor
            The 'p' part of the head entity embedding in Clifford algebra.
        rp : torch.Tensor
            The 'p' part of the relation embedding in Clifford algebra.

        Returns
        -------
        sigma_pp : torch.Tensor
            The sigma_pp component of the Clifford multiplication.
        """
        # Compute indexes for the upper triangle of p by p matrix
        indices = torch.triu_indices(self.p, self.p, offset=1)
        # Compute p by p operations
        sigma_pp = torch.einsum("nrp,nrx->nrpx", hp, rp) - torch.einsum(
            "nrx,nrp->nrpx", hp, rp
        )
        sigma_pp = sigma_pp[:, :, indices[0], indices[1]]
        return sigma_pp

    def compute_sigma_qq(self, hq: torch.Tensor, rq: torch.Tensor) -> torch.Tensor:
        """
        Computes the sigma_qq component in Clifford multiplication, representing the interactions
        between the negative square terms in the Clifford algebra.

        TODO: Add mathematical format for sphinx.

        sigma_{qq} = \sum_{j=1}^{p+q-1} \sum_{k=j+1}^{p+q} (h_j r_k - h_k r_j) e_j e_k
        sigma_{q} captures the interactions between along q bases
        For instance, let q e_1, e_2, e_3, we compute interactions between e_1 e_2, e_1 e_3 , and e_2 e_3
        This can be implemented with a nested two for loops

                        results = []
                        for j in range(q - 1):
                            for k in range(j + 1, q):
                                results.append(hq[:, :, j] * rq[:, :, k] - hq[:, :, k] * rq[:, :, j])
                        sigma_qq = torch.stack(results, dim=2)
                        assert sigma_qq.shape == (b, r, int((q * (q - 1)) / 2))

        Yet, this computation would be quite inefficient. Instead, we compute interactions along all p,
        e.g., e1e1, e1e2, e1e3,
              e2e1, e2e2, e2e3,
              e3e1, e3e2, e3e3
        Then select the triangular matrix without diagonals: e1e2, e1e3, e2e3.

        Parameters
        ----------
        hq : torch.Tensor
            The 'q' part of the head entity embedding in Clifford algebra.
        rq : torch.Tensor
            The 'q' part of the relation embedding in Clifford algebra.

        Returns
        -------
        sigma_qq : torch.Tensor
            The sigma_qq component of the Clifford multiplication.
        """
        # Compute indexes for the upper triangle of p by p matrix
        if self.q > 1:
            indices = torch.triu_indices(self.q, self.q, offset=1)
            # Compute p by p operations
            sigma_qq = torch.einsum("nrp,nrx->nrpx", hq, rq) - torch.einsum(
                "nrx,nrp->nrpx", hq, rq
            )
            sigma_qq = sigma_qq[:, :, indices[0], indices[1]]
        else:
            sigma_qq = torch.zeros((len(hq), self.r, int((self.q * (self.q - 1)) / 2)))

        return sigma_qq

    def compute_sigma_pq(
        self, *, hp: torch.Tensor, hq: torch.Tensor, rp: torch.Tensor, rq: torch.Tensor
    ) -> torch.Tensor:
        """
        Computes the sigma_pq component in Clifford multiplication, representing the interactions
        between the positive and negative square terms in the Clifford algebra.

        TODO: Add mathematical format for sphinx.
        
        \sum_{i=1}^{p} \sum_{j=p+1}^{p+q} (h_i r_j - h_j r_i) e_i e_j

        # results = []
        # sigma_pq = torch.zeros(b, r, p, q)
        # for i in range(p):
        #     for j in range(q):
        #         sigma_pq[:, :, i, j] = hp[:, :, i] * rq[:, :, j] - hq[:, :, j] * rp[:, :, i]
        # print(sigma_pq.shape)

        Parameters
        ----------
        hp : torch.Tensor
            The 'p' part of the head entity embedding in Clifford algebra.
        hq : torch.Tensor
            The 'q' part of the head entity embedding in Clifford algebra.
        rp : torch.Tensor
            The 'p' part of the relation embedding in Clifford algebra.
        rq : torch.Tensor
            The 'q' part of the relation embedding in Clifford algebra.

        Returns
        -------
        sigma_pq : torch.Tensor
            The sigma_pq component of the Clifford multiplication.
        """
        sigma_pq = torch.einsum("nrp,nrq->nrpq", hp, rq) - torch.einsum(
            "nrq,nrp->nrpq", hq, rp
        )
        assert sigma_pq.shape[1:] == (self.r, self.p, self.q)
        return sigma_pq

    def apply_coefficients(
        self,
        h0: torch.Tensor,
        hp: torch.Tensor,
        hq: torch.Tensor,
        r0: torch.Tensor,
        rp: torch.Tensor,
        rq: torch.Tensor,
    ) -> tuple[
        torch.FloatTensor,
        torch.FloatTensor,
        torch.FloatTensor,
        torch.FloatTensor,
        torch.FloatTensor,
        torch.FloatTensor,
    ]:
        """
        Applies scaling coefficients to the base vectors in the Clifford algebra.
        This method is used for adjusting the contributions of different components in the algebra.

        Parameters
        ----------
        h0 : torch.Tensor
            The scalar part of the head entity embedding.
        hp : torch.Tensor
            The 'p' part of the head entity embedding.
        hq : torch.Tensor
            The 'q' part of the head entity embedding.
        r0 : torch.Tensor
            The scalar part of the relation embedding.
        rp : torch.Tensor
            The 'p' part of the relation embedding.
        rq : torch.Tensor
            The 'q' part of the relation embedding.

        Returns
        -------
        tuple
            Tuple containing the scaled components of the head and relation embeddings.
        """
        if self.p > 0:
            hp = hp * self.p_coefficients.weight
            rp = rp * self.p_coefficients.weight
        if self.q > 0:
            hq = hq * self.q_coefficients.weight
            rq = rq * self.q_coefficients.weight
        return h0, hp, hq, r0, rp, rq

    def clifford_multiplication(
        self,
        h0: torch.Tensor,
        hp: torch.Tensor,
        hq: torch.Tensor,
        r0: torch.Tensor,
        rp: torch.Tensor,
        rq: torch.Tensor,
    ) -> tuple[
        torch.FloatTensor,
        torch.FloatTensor,
        torch.FloatTensor,
        torch.FloatTensor,
        torch.FloatTensor,
        torch.FloatTensor,
    ]:
        """
        Performs Clifford multiplication of head and relation embeddings. This method computes the
        various components of the Clifford product, combining the scalar, 'p', and 'q' parts of the embeddings.

        TODO: Add mathematical format for sphinx.

        h = h_0 + \sum_{i=1}^p h_i e_i + \sum_{j=p+1}^{p+q} h_j e_j
        r = r_0 + \sum_{i=1}^p r_i e_i + \sum_{j=p+1}^{p+q} r_j e_j

        ei ^2 = +1     for i =< i =< p
        ej ^2 = -1     for p < j =< p+q
        ei ej = -eje1  for i \neq j

        h r =   sigma_0 + sigma_p + sigma_q + sigma_{pp} + sigma_{q}+ sigma_{pq}
        where
                (1) sigma_0 = h_0 r_0 + \sum_{i=1}^p (h_0 r_i) e_i - \sum_{j=p+1}^{p+q} (h_j r_j) e_j

                (2) sigma_p = \sum_{i=1}^p (h_0 r_i + h_i r_0) e_i

                (3) sigma_q = \sum_{j=p+1}^{p+q} (h_0 r_j + h_j r_0) e_j

                (4) sigma_{pp} = \sum_{i=1}^{p-1} \sum_{k=i+1}^p (h_i r_k - h_k r_i) e_i e_k

                (5) sigma_{qq} = \sum_{j=1}^{p+q-1} \sum_{k=j+1}^{p+q} (h_j r_k - h_k r_j) e_j e_k

                (6) sigma_{pq} = \sum_{i=1}^{p} \sum_{j=p+1}^{p+q} (h_i r_j - h_j r_i) e_i e_j

        Parameters
        ----------
        h0 : torch.Tensor
            The scalar part of the head entity embedding.
        hp : torch.Tensor
            The 'p' part of the head entity embedding.
        hq : torch.Tensor
            The 'q' part of the head entity embedding.
        r0 : torch.Tensor
            The scalar part of the relation embedding.
        rp : torch.Tensor
            The 'p' part of the relation embedding.
        rq : torch.Tensor
            The 'q' part of the relation embedding.

        Returns
        -------
        tuple
            Tuple containing the components of the Clifford product.

        """
        n = len(h0)
        assert h0.shape == (n, self.r) == r0.shape == (n, self.r)
        assert hp.shape == (n, self.r, self.p) == rp.shape == (n, self.r, self.p)
        assert hq.shape == (n, self.r, self.q) == rq.shape == (n, self.r, self.q)
        # (1)
        sigma_0 = h0 * r0 + torch.sum(hp * rp, dim=2) - torch.sum(hq * rq, dim=2)
        assert sigma_0.shape == (n, self.r)
        # (2)
        sigma_p = torch.einsum("nr,nrp->nrp", h0, rp) + torch.einsum(
            "nr,nrp->nrp", r0, hp
        )
        assert sigma_p.shape == (n, self.r, self.p)
        # (3)
        sigma_q = torch.einsum("nr,nrq->nrq", h0, rq) + torch.einsum(
            "nr,nrq->nrq", r0, hq
        )
        # (4)
        sigma_pp = self.compute_sigma_pp(hp, rp)
        # (5)
        sigma_qq = self.compute_sigma_qq(hq, rq)
        # (6)
        sigma_pq = torch.einsum("bkp,bkq->bkpq", hp, rq) - torch.einsum(
            "bkp,bkq->bkpq", rp, hq
        )
        assert sigma_pq.shape == (n, self.r, self.p, self.q)

        return sigma_0, sigma_p, sigma_q, sigma_pp, sigma_qq, sigma_pq

    def construct_cl_multivector(
        self, x: torch.FloatTensor, r: int, p: int, q: int
    ) -> tuple[torch.FloatTensor, torch.FloatTensor, torch.FloatTensor]:
        """
        Construct a batch of multivectors Cl_{p,q}(\mathbb{R}^d)

        Parameter
        ---------
        x : torch.FloatTensor
            The embedding vector with shape (n, d).
        r : int
            The dimension of the scalar part.
        p : int
            The number of positive square terms.
        q : int
            The number of negative square terms.

        Returns
        -------
        a0 : torch.FloatTensor
            Tensor with (n,r) shape
        ap : torch.FloatTensor
            Tensor with (n,r,p) shape
        aq : torch.FloatTensor
            Tensor with (n,r,q) shape
        """
        batch_size, d = x.shape
        # (1) A_{n \times k}: take the first k columns
        a0 = x[:, :r].view(batch_size, r)
        # (2) B_{n \times p}, C_{n \times q}: take the self.k * self.p columns after the k. column
        if p > 0:
            ap = x[:, r : r + (r * p)].view(batch_size, r, p)
        else:
            ap = torch.zeros((batch_size, r, p), device=self.device)
        if q > 0:
            # (3) B_{n \times p}, C_{n \times q}: take the last self.r * self.q .
            aq = x[:, -(r * q) :].view(batch_size, r, q)
        else:
            aq = torch.zeros((batch_size, r, q), device=self.device)
        return a0, ap, aq

    def forward_k_vs_with_explicit(self, x: torch.Tensor) -> torch.FloatTensor:
        """
        Computes scores for a batch of triples against all entities using explicit Clifford multiplication.
        This method is used for K-vs-All training and evaluation.

        Parameters
        ----------
        x : torch.Tensor
            Tensor representing a batch of head entities and relations.

        Returns
        -------
        torch.FloatTensor
            A tensor containing scores for each triple against all entities.
        """
        n = len(x)
        # (1) Retrieve real-valued embedding vectors.
        head_ent_emb, rel_ent_emb = self.get_head_relation_representation(x)
        # (2) Construct multi-vector in Cl_{p,q} (\mathbb{R}^d) for head entities and relations
        h0, hp, hq = self.construct_cl_multivector(
            head_ent_emb, r=self.r, p=self.p, q=self.q
        )
        r0, rp, rq = self.construct_cl_multivector(
            rel_ent_emb, r=self.r, p=self.p, q=self.q
        )
        E = self.entity_embeddings.weight

        # Clifford mul.
        sigma_0 = h0 * r0 + torch.sum(hp * rp, dim=2) - torch.sum(hq * rq, dim=2)
        sigma_p = torch.einsum("nr,nrp->nrp", h0, rp) + torch.einsum(
            "nrp, nr->nrp", hp, r0
        )
        sigma_q = torch.einsum("nr,nrq->nrq", h0, rq) + torch.einsum(
            "nrq, nr->nrq", hq, r0
        )

        t0 = E[:, : self.r]

        score_sigma_0 = sigma_0 @ t0.transpose(1, 0)
        if self.p > 0:
            tp = E[:, self.r : self.r + (self.r * self.p)].view(
                self.num_entities, self.r, self.p
            )
            score_sigma_p = torch.einsum("bkp,ekp->be", sigma_p, tp)
        else:
            score_sigma_p = 0
        if self.q > 0:
            tq = E[:, -(self.r * self.q) :].view(self.num_entities, self.r, self.q)
            score_sigma_q = torch.einsum("bkp,ekp->be", sigma_q, tq)
        else:
            score_sigma_q = 0

        # Compute sigma_pp sigma_qq and sigma_pq
        if self.p > 1:
            results = []
            for i in range(self.p - 1):
                for k in range(i + 1, self.p):
                    results.append(
                        hp[:, :, i] * rp[:, :, k] - hp[:, :, k] * rp[:, :, i]
                    )
            sigma_pp = torch.stack(results, dim=2)
            assert sigma_pp.shape == (n, self.r, int((self.p * (self.p - 1)) / 2))
            sigma_pp = torch.sum(sigma_pp, dim=[1, 2]).view(n, 1)
            del results
        else:
            sigma_pp = 0

        if self.q > 1:
            results = []
            for j in range(self.q - 1):
                for k in range(j + 1, self.q):
                    results.append(
                        hq[:, :, j] * rq[:, :, k] - hq[:, :, k] * rq[:, :, j]
                    )
            sigma_qq = torch.stack(results, dim=2)
            del results
            assert sigma_qq.shape == (n, self.r, int((self.q * (self.q - 1)) / 2))
            sigma_qq = torch.sum(sigma_qq, dim=[1, 2]).view(n, 1)
        else:
            sigma_qq = 0

        if self.p >= 1 and self.q >= 1:
            sigma_pq = torch.zeros(n, self.r, self.p, self.q)
            for i in range(self.p):
                for j in range(self.q):
                    sigma_pq[:, :, i, j] = (
                        hp[:, :, i] * rq[:, :, j] - hq[:, :, j] * rp[:, :, i]
                    )
            sigma_pq = torch.sum(sigma_pq, dim=[1, 2, 3]).view(n, 1)
        else:
            sigma_pq = 0

        return (
            score_sigma_0
            + score_sigma_p
            + score_sigma_q
            + sigma_pp
            + sigma_qq
            + sigma_pq
        )

    def k_vs_all_score(
        self,
        bpe_head_ent_emb: torch.Tensor,
        bpe_rel_ent_emb: torch.Tensor,
        E: torch.Tensor,
    ) -> torch.FloatTensor:
        """
        Computes scores for all triples using Clifford multiplication in a K-vs-All setup. This method involves constructing
        multivectors for head entities and relations in Clifford algebra, applying coefficients, and computing interaction
        scores based on different components of the Clifford algebra.

        Parameters
        ----------
        bpe_head_ent_emb : torch.Tensor
            Batch of head entity embeddings in BPE (Byte Pair Encoding) format. Tensor shape: (batch_size, embedding_dim).
        bpe_rel_ent_emb : torch.Tensor
            Batch of relation embeddings in BPE format. Tensor shape: (batch_size, embedding_dim).
        E : torch.Tensor
            Tensor containing all entity embeddings. Tensor shape: (num_entities, embedding_dim).

        Returns
        -------
        torch.FloatTensor
            Tensor containing the scores for each triple in the K-vs-All setting. Tensor shape: (batch_size, num_entities).

        Notes
        -----
        The method computes scores based on the basis of 1 (scalar part), the bases of 'p' (positive square terms),
        and the bases of 'q' (negative square terms). Additional computations involve sigma_pp, sigma_qq, and sigma_pq
        components in Clifford multiplication, corresponding to different interaction terms.
        """

        # (2) Construct multi-vector in Cl_{p,q} (\mathbb{R}^d) for head entities and relations
        h0, hp, hq = self.construct_cl_multivector(
            bpe_head_ent_emb, r=self.r, p=self.p, q=self.q
        )
        r0, rp, rq = self.construct_cl_multivector(
            bpe_rel_ent_emb, r=self.r, p=self.p, q=self.q
        )

        h0, hp, hq, h0, rp, rq = self.apply_coefficients(h0, hp, hq, h0, rp, rq)
        # (3.1) Extract real part
        t0 = E[:, : self.r]

        num_entities = len(E)
        # (4) Compute a triple score based on interactions described by the basis 1. Eq. 20
        h0r0t0 = torch.einsum("br,er->be", h0 * r0, t0)

        # (5) Compute a triple score based on interactions described by the bases of p {e_1, ..., e_p}. Eq. 21
        if self.p > 0:
            tp = E[:, self.r : self.r + (self.r * self.p)].view(
                num_entities, self.r, self.p
            )
            hp_rp_t0 = torch.einsum("brp, er  -> be", hp * rp, t0)
            h0_rp_tp = torch.einsum(
                "brp, erp -> be", torch.einsum("br,  brp -> brp", h0, rp), tp
            )
            hp_r0_tp = torch.einsum(
                "brp, erp -> be", torch.einsum("brp, br  -> brp", hp, r0), tp
            )
            score_p = hp_rp_t0 + h0_rp_tp + hp_r0_tp
        else:
            score_p = 0

        # (5) Compute a triple score based on interactions described by the bases of q {e_{p+1}, ..., e_{p+q}}. Eq. 22
        if self.q > 0:
            tq = E[:, -(self.r * self.q) :].view(num_entities, self.r, self.q)
            h0_rq_tq = torch.einsum(
                "brq, erq -> be", torch.einsum("br,  brq -> brq", h0, rq), tq
            )
            hq_r0_tq = torch.einsum(
                "brq, erq -> be", torch.einsum("brq, br  -> brq", hq, r0), tq
            )
            hq_rq_t0 = torch.einsum("brq, er  -> be", hq * rq, t0)
            score_q = h0_rq_tq + hq_r0_tq - hq_rq_t0
        else:
            score_q = 0

        if self.p >= 2:
            sigma_pp = torch.sum(self.compute_sigma_pp(hp, rp), dim=[1, 2]).unsqueeze(
                -1
            )
        else:
            sigma_pp = 0

        if self.q >= 2:
            sigma_qq = torch.sum(self.compute_sigma_qq(hq, rq), dim=[1, 2]).unsqueeze(
                -1
            )
        else:
            sigma_qq = 0

        if self.p >= 2 and self.q >= 2:
            sigma_pq = torch.sum(
                self.compute_sigma_pq(hp=hp, hq=hq, rp=rp, rq=rq), dim=[1, 2, 3]
            ).unsqueeze(-1)
        else:
            sigma_pq = 0
        return h0r0t0 + score_p + score_q + sigma_pp + sigma_qq + sigma_pq

    def forward_k_vs_all(self, x: torch.Tensor) -> torch.FloatTensor:
        """
        TODO: Add mathematical format for sphinx.
        Performs the forward pass for K-vs-All training and evaluation in knowledge graph embeddings.
        This method involves retrieving real-valued embedding vectors for head entities and relations \mathbb{R}^d,
        constructing Clifford algebra multivectors for these embeddings according to Cl_{p,q}(\mathbb{R}^d), performing Clifford multiplication,
        and computing the inner product with all entity embeddings.

        Parameters
        ----------
        x : torch.Tensor
            A tensor representing a batch of head entities and relations for the K-vs-All evaluation.
            Expected tensor shape: (n, 2), where 'n' is the batch size and '2' represents head entity
            and relation pairs.

        Returns
        -------
        torch.FloatTensor
            A tensor containing the scores for each head entity and relation pair against all possible
            tail entities in the knowledge graph. Tensor shape: (n, |E|), where '|E|' is the number
            of entities in the knowledge graph.

        Notes
        -----
        This method is similar to the 'forward_k_vs_with_explicit' function in functionality. It is
        typically used in scenarios where every possible combination of a head entity and a relation
        is scored against all tail entities, commonly used in knowledge graph completion tasks.
        """
        # (1) Retrieve real-valued embedding vectors.
        head_ent_emb, rel_ent_emb = self.get_head_relation_representation(x)

        # (3) Extract all entity embeddings
        E = self.entity_embeddings.weight
        return self.k_vs_all_score(head_ent_emb, rel_ent_emb, E)

    def forward_k_vs_sample(
        self, x: torch.LongTensor, target_entity_idx: torch.LongTensor
    ) -> torch.FloatTensor:
        """
        
        TODO: Add mathematical format for sphinx.

        Performs the forward pass for K-vs-Sample training in knowledge graph embeddings. This method involves
        retrieving real-valued embedding vectors for head entities and relations \mathbb{R}^d, constructing Clifford algebra
        multivectors for these embeddings according to Cl_{p,q}(\mathbb{R}^d), performing Clifford multiplication,
        and computing the inner product with a sampled subset of entity embeddings.

        Parameters
        ----------
        x : torch.LongTensor
            A tensor representing a batch of head entities and relations for the K-vs-Sample evaluation.
            Expected tensor shape: (n, 2), where 'n' is the batch size and '2' represents head entity
            and relation pairs.
        target_entity_idx : torch.LongTensor
            A tensor of target entity indices for sampling in the K-vs-Sample evaluation.
            Tensor shape: (n, sample_size), where 'sample_size' is the number of entities sampled.

        Returns
        -------
        torch.FloatTensor
            A tensor containing the scores for each head entity and relation pair against the sampled
            subset of tail entities. Tensor shape: (n, sample_size).

        Notes
        -----
        This method is used in scenarios where every possible combination of a head entity and a relation
        is scored against a sampled subset of tail entities, commonly used in knowledge graph completion tasks
        with a large number of entities.
        """
        # (1) Retrieve real-valued embedding vectors.
        head_ent_emb, rel_emb = self.get_head_relation_representation(x)
        # (2) Construct multi-vector in Cl_{p,q} (\mathbb{R}^d) for head entities.
        a0, ap, aq = self.construct_cl_multivector(
            head_ent_emb, r=self.r, p=self.p, q=self.q
        )
        # (2) Construct multi-vector in Cl_{p,q} (\mathbb{R}^d) for relations.
        b0, bp, bq = self.construct_cl_multivector(
            rel_emb, r=self.r, p=self.p, q=self.q
        )

        # (4) Clifford multiplication of (2) and (3).
        # AB_pp, AB_qq, AB_pq
        # AB_0, AB_p, AB_q, AB_pp, AB_qq, AB_pq = self.clifford_mul_reduced_interactions(a0, ap, aq, b0, bp, bq)
        AB_0, AB_p, AB_q, AB_pp, AB_qq, AB_pq = self.clifford_mul(
            a0, ap, aq, b0, bp, bq
        )

        # b e r
        selected_tail_entity_embeddings = self.entity_embeddings(target_entity_idx)
        # (7) Inner product of AB_0 and a0 of all entities.
        A_score = torch.einsum(
            "br,ber->be", AB_0, selected_tail_entity_embeddings[:, : self.r]
        )

        # (8) Inner product of AB_p and ap of all entities.
        if self.p > 0:
            B_score = torch.einsum(
                "brp,berp->be",
                AB_p,
                selected_tail_entity_embeddings[
                    :, self.r : self.r + (self.r * self.p)
                ].view(self.num_entities, self.r, self.p),
            )
        else:
            B_score = 0
        # (9) Inner product of AB_q and aq of all entities.
        if self.q > 0:
            C_score = torch.einsum(
                "brq,berq->be",
                AB_q,
                selected_tail_entity_embeddings[:, -(self.r * self.q) :].view(
                    self.num_entities, self.r, self.q
                ),
            )
        else:
            C_score = 0
        # (10) Aggregate (7,8,9).
        A_B_C_score = A_score + B_score + C_score
        # (11) Compute inner products of AB_pp, AB_qq, AB_pq and respective identity matrices of all entities.
        D_E_F_score = (
            torch.einsum("brpp->b", AB_pp)
            + torch.einsum("brqq->b", AB_qq)
            + torch.einsum("brpq->b", AB_pq)
        )
        D_E_F_score = D_E_F_score.view(len(head_ent_emb), 1)
        # (12) Score
        return A_B_C_score + D_E_F_score

    def score(
        self, h: torch.Tensor, r: torch.Tensor, t: torch.Tensor
    ) -> torch.FloatTensor:
        """
        Computes the score for a given triple using Clifford multiplication in the context of knowledge graph embeddings.
        This method involves constructing Clifford algebra multivectors for head entities, relations, and tail entities,
        applying coefficients, and computing interaction scores based on different components of the Clifford algebra.

        Parameters
        ----------
        h : torch.Tensor
            Tensor representing the embeddings of head entities. Expected shape: (n, d), where 'n' is the number of triples
            and 'd' is the embedding dimension.
        r : torch.Tensor
            Tensor representing the embeddings of relations. Expected shape: (n, d).
        t : torch.Tensor
            Tensor representing the embeddings of tail entities. Expected shape: (n, d).

        Returns
        -------
        torch.FloatTensor
            Tensor containing the scores for each triple. Tensor shape: (n,).

        Notes
        -----
        The method computes scores based on the scalar part, the bases of 'p' (positive square terms),
        and the bases of 'q' (negative square terms) in Clifford algebra. It includes additional computations
        involving sigma_pp, sigma_qq, and sigma_pq components, which correspond to different interaction terms
        in the Clifford product.
        """
        # (2) Construct multi-vector in Cl_{p,q} (\mathbb{R}^d) for head entities and relations
        h0, hp, hq = self.construct_cl_multivector(h, r=self.r, p=self.p, q=self.q)
        r0, rp, rq = self.construct_cl_multivector(r, r=self.r, p=self.p, q=self.q)
        t0, tp, tq = self.construct_cl_multivector(t, r=self.r, p=self.p, q=self.q)

        if self.q > 0:
            self.q_coefficients = self.q_coefficients.to(h0.device, non_blocking=True)

        h0, hp, hq, h0, rp, rq = self.apply_coefficients(h0, hp, hq, h0, rp, rq)
        # (4) Compute a triple score based on interactions described by the basis 1. Eq. 20
        h0r0t0 = torch.einsum("br, br -> b", h0 * r0, t0)

        # (5) Compute a triple score based on interactions described by the bases of p {e_1, ..., e_p}. Eq. 21
        if self.p > 0:
            # Second term in Eq.16
            hp_rp_t0 = torch.einsum("brp, br  -> b", hp * rp, t0)
            # Eq. 17
            # b=e
            h0_rp_tp = torch.einsum(
                "brp, erp -> b", torch.einsum("br,  brp -> brp", h0, rp), tp
            )
            hp_r0_tp = torch.einsum(
                "brp, erp -> b", torch.einsum("brp, br  -> brp", hp, r0), tp
            )

            score_p = hp_rp_t0 + h0_rp_tp + hp_r0_tp
        else:
            score_p = 0

        # (5) Compute a triple score based on interactions described by the bases of q {e_{p+1}, ..., e_{p+q}}. Eq. 22
        if self.q > 0:
            # Third item in Eq 16.
            hq_rq_t0 = torch.einsum("brq, br  -> b", hq * rq, t0)
            # Eq. 18.
            h0_rq_tq = torch.einsum("br, brq  -> b", h0, rq * tq)
            r0_hq_tq = torch.einsum("br, brq  -> b", r0, hq * tq)
            score_q = -hq_rq_t0 + (h0_rq_tq + r0_hq_tq)
        else:
            score_q = 0

        if self.p >= 2:
            sigma_pp = torch.sum(self.compute_sigma_pp(hp, rp), dim=[1, 2]).unsqueeze(
                -1
            )
        else:
            sigma_pp = 0

        if self.q >= 2:
            sigma_qq = torch.sum(self.compute_sigma_qq(hq, rq), dim=[1, 2]).unsqueeze(
                -1
            )
        else:
            sigma_qq = 0

        if self.p >= 2 and self.q >= 2:
            sigma_pq = torch.sum(
                self.compute_sigma_pq(hp=hp, hq=hq, rp=rp, rq=rq), dim=[1, 2, 3]
            ).unsqueeze(-1)
        else:
            sigma_pq = 0
        return h0r0t0 + score_p + score_q + sigma_pp + sigma_qq + sigma_pq

    def forward_triples(self, x: torch.Tensor) -> torch.FloatTensor:
        """
        Computes scores for a batch of triples using Clifford multiplication.
        This method is involved in the forward pass of the model during training or evaluation.
        It retrieves embeddings for head entities, relations, and tail entities, constructs Clifford algebra multivectors,
        applies coefficients, and computes interaction scores based on different components of Clifford algebra.

        Parameters
        ----------
        x : torch.Tensor
            A tensor representing a batch of triples. Each triple consists of indices for a head entity, a relation, and a tail entity.
            Expected tensor shape: (n, 3), where 'n' is the number of triples.

        Returns
        -------
        torch.FloatTensor
            A tensor containing the scores for each triple in the batch. Tensor shape: (n,), where 'n' is the number of triples.

        Notes
        -----
        The method computes scores based on the scalar part, the bases of 'p' (positive square terms), and the bases of 'q' (negative square terms) in Clifford algebra.
        It includes additional computations involving sigma_pp, sigma_qq, and sigma_pq components, corresponding to different interaction terms in the Clifford product.
        """
        # (1) Retrieve real-valued embedding vectors.
        head_ent_emb, rel_ent_emb, tail_ent_emb = self.get_triple_representation(x)
        # (2) Construct multi-vector in Cl_{p,q} (\mathbb{R}^d) for head entities and relations
        h0, hp, hq = self.construct_cl_multivector(
            head_ent_emb, r=self.r, p=self.p, q=self.q
        )
        r0, rp, rq = self.construct_cl_multivector(
            rel_ent_emb, r=self.r, p=self.p, q=self.q
        )
        t0, tp, tq = self.construct_cl_multivector(
            tail_ent_emb, r=self.r, p=self.p, q=self.q
        )
        h0, hp, hq, h0, rp, rq = self.apply_coefficients(h0, hp, hq, h0, rp, rq)
        # (4) Compute a triple score based on interactions described by the basis 1. Eq. 20
        h0r0t0 = torch.einsum("br, br -> b", h0 * r0, t0)

        # (5) Compute a triple score based on interactions described by the bases of p {e_1, ..., e_p}. Eq. 21
        if self.p > 0:
            # Second term in Eq.16
            hp_rp_t0 = torch.einsum("brp, br  -> b", hp * rp, t0)
            # Eq. 17
            # b=e
            h0_rp_tp = torch.einsum(
                "brp, erp -> b", torch.einsum("br,  brp -> brp", h0, rp), tp
            )
            hp_r0_tp = torch.einsum(
                "brp, erp -> b", torch.einsum("brp, br  -> brp", hp, r0), tp
            )

            score_p = hp_rp_t0 + h0_rp_tp + hp_r0_tp
        else:
            score_p = 0

        # (5) Compute a triple score based on interactions described by the bases of q {e_{p+1}, ..., e_{p+q}}. Eq. 22
        if self.q > 0:
            # Third item in Eq 16.
            hq_rq_t0 = torch.einsum("brq, br  -> b", hq * rq, t0)
            # Eq. 18.
            h0_rq_tq = torch.einsum("br, brq  -> b", h0, rq * tq)
            r0_hq_tq = torch.einsum("br, brq  -> b", r0, hq * tq)
            score_q = -hq_rq_t0 + (h0_rq_tq + r0_hq_tq)
        else:
            score_q = 0

        if self.p >= 2:
            sigma_pp = torch.sum(self.compute_sigma_pp(hp, rp), dim=[1, 2]).unsqueeze(
                -1
            )
        else:
            sigma_pp = 0

        if self.q >= 2:
            sigma_qq = torch.sum(self.compute_sigma_qq(hq, rq), dim=[1, 2]).unsqueeze(
                -1
            )
        else:
            sigma_qq = 0

        if self.p >= 2 and self.q >= 2:
            sigma_pq = torch.sum(
                self.compute_sigma_pq(hp=hp, hq=hq, rp=rp, rq=rq), dim=[1, 2, 3]
            ).unsqueeze(-1)
        else:
            sigma_pq = 0
        return h0r0t0 + score_p + score_q + sigma_pp + sigma_qq + sigma_pq


class KeciBase(Keci):
    """
    The KeciBase class is a variant of the Keci class for knowledge graph embeddings, with the key difference being
    the lack of learning for dimension scaling. It inherits the core functionality from the Keci class but sets
    the gradient requirement for interaction coefficients to False, indicating these coefficients are not updated
    during training.

    Parameters
    ----------
    args : dict
        A dictionary of arguments containing hyperparameters and settings for the model, including 'p', 'q',
        and embedding dimensions.

    Attributes
    ----------
    name : str
        The name identifier for the KeciBase class.
    requires_grad_for_interactions : bool
        Flag to indicate if the interaction coefficients require gradients. In KeciBase, this is set to False.
    p_coefficients : torch.nn.Embedding (optional)
        Embedding for scaling coefficients of 'p' terms, initialized to ones if 'p' > 0.
    q_coefficients : torch.nn.Embedding (optional)
        Embedding for scaling coefficients of 'q' terms, initialized to ones if 'q' > 0.

    Notes
    -----
    KeciBase is designed for scenarios where fixed coefficients are preferred over learnable parameters
    for dimension scaling in the Clifford algebra-based embedding interactions.
    """

    def __init__(self, args):
        super().__init__(args)
        self.name = "KeciBase"
        self.requires_grad_for_interactions = False
        print(f"r:{self.r}\t p:{self.p}\t q:{self.q}")
        if self.p > 0:
            self.p_coefficients = torch.nn.Embedding(
                num_embeddings=1, embedding_dim=self.p
            )
            torch.nn.init.ones_(self.p_coefficients.weight)
        if self.q > 0:
            self.q_coefficients = torch.nn.Embedding(
                num_embeddings=1, embedding_dim=self.q
            )
            torch.nn.init.ones_(self.q_coefficients.weight)


class DeCaL(BaseKGE):
    def __init__(self, args):
        super().__init__(args)
        self.name = 'DeCaL'
        self.entity_embeddings = torch.nn.Embedding(self.num_entities, self.embedding_dim)
        self.relation_embeddings = torch.nn.Embedding(self.num_relations, self.embedding_dim)
        self.p = self.args.get("p", 0)
        self.q = self.args.get("q", 0)
        self.r = self.args.get("r", 0)
        self.re = int(self.embedding_dim / (self.r + self.p + self.q + 1))

        # Initialize parameters for dimension scaling
        if self.p > 0:
            self.p_coefficients = torch.nn.Embedding(num_embeddings=1, embedding_dim=self.p)
            torch.nn.init.zeros_(self.p_coefficients.weight)
        if self.q > 0:
            self.q_coefficients = torch.nn.Embedding(num_embeddings=1, embedding_dim=self.q)
            torch.nn.init.zeros_(self.q_coefficients.weight)
        if self.r > 0:
            self.r_coefficients = torch.nn.Embedding(num_embeddings=1, embedding_dim=self.r)
            torch.nn.init.zeros_(self.r_coefficients.weight)

    def forward_triples(self, x: torch.Tensor) -> torch.FloatTensor:
        """

        Parameter
        ---------
        x: torch.LongTensor with (n,3) shape

        Returns
        -------
        torch.FloatTensor with (n) shape
        """
        # (1) Retrieve real-valued embedding vectors.
        head_ent_emb, rel_ent_emb, tail_ent_emb = self.get_triple_representation(x)
        # (2) Construct multi-vector in Cl_{p,q} (\mathbb{R}^d) for head entities and relations
        h0, hp, hq = self.construct_cl_multivector(head_ent_emb, r=self.r, p=self.p, q=self.q)
        r0, rp, rq = self.construct_cl_multivector(rel_ent_emb, r=self.r, p=self.p, q=self.q)
        t0, tp, tq = self.construct_cl_multivector(tail_ent_emb, r=self.r, p=self.p, q=self.q)
        h0, hp, hq, h0, rp, rq = self.apply_coefficients(h0, hp, hq, h0, rp, rq)
        # (4) Compute a triple score based on interactions described by the basis 1. Eq. 20
        h0r0t0 = torch.einsum('br, br -> b', h0 * r0, t0)

        # (5) Compute a triple score based on interactions described by the bases of p {e_1, ..., e_p}.
        if self.p > 0:
            # Second term in Eq.16
            hp_rp_t0 = torch.einsum('brp, br  -> b', hp * rp, t0)
            # Eq. 17
            # b=e
            h0_rp_tp = torch.einsum('brp, erp -> b', torch.einsum('br,  brp -> brp', h0, rp), tp)
            hp_r0_tp = torch.einsum('brp, erp -> b', torch.einsum('brp, br  -> brp', hp, r0), tp)

            score_p = hp_rp_t0 + h0_rp_tp + hp_r0_tp
        else:
            score_p = 0

        # (5) Compute a triple score based on interactions described by the bases of q {e_{p+1}, ..., e_{p+q}}. Eq. 22
        if self.q > 0:
            # Third item in Eq 16.
            hq_rq_t0 = torch.einsum('brq, br  -> b', hq * rq, t0)
            # Eq. 18.
            h0_rq_tq = torch.einsum('br, brq  -> b', h0, rq * tq)
            r0_hq_tq = torch.einsum('br, brq  -> b', r0, hq * tq)
            score_q = - hq_rq_t0 + (h0_rq_tq + r0_hq_tq)
        else:
            score_q = 0

        if self.r > 0:
            # Eq. 18.
            h0_rk_tk = torch.einsum('br, brk  -> b', h0, rk * tk)
            r0_hk_tk = torch.einsum('br, brk  -> b', r0, hk * tk)
            score_r = (h0_rk_tk + r0_hk_tk)
        else:
            score_r = 0

        if self.p >= 2:
            sigma_pp = torch.sum(self.compute_sigma_pp(hp, rp), dim=[1, 2]).unsqueeze(-1)
        else:
            sigma_pp = 0

        if self.q >= 2:
            sigma_qq = torch.sum(self.compute_sigma_qq(hq, rq), dim=[1, 2]).unsqueeze(-1)
        else:
            sigma_qq = 0

        if self.r >= 2:
            sigma_rr = torch.sum(self.compute_sigma_qq(hk, rk), dim=[1, 2]).unsqueeze(-1)
        else:
            sigma_rr = 0

        if self.p >= 2 and self.q >= 2:
            sigma_pq = torch.sum(self.compute_sigma_pq(hp=hp, hq=hq, rp=rp, rq=rq), dim=[1, 2, 3]).unsqueeze(-1)
        else:
            sigma_pq = 0
        return h0r0t0 + score_p + score_q + sigma_pp + sigma_qq + sigma_pq


class KeciBase(Keci):
    " Without learning dimension scaling"

    def __init__(self, args):
        super().__init__(args)
        self.name = 'KeciBase'
        self.requires_grad_for_interactions = False
        print(f'r:{self.r}\t p:{self.p}\t q:{self.q}')
        if self.p > 0:
            self.p_coefficients = torch.nn.Embedding(num_embeddings=1, embedding_dim=self.p)
            torch.nn.init.ones_(self.p_coefficients.weight)
        if self.q > 0:
            self.q_coefficients = torch.nn.Embedding(num_embeddings=1, embedding_dim=self.q)
            torch.nn.init.ones_(self.q_coefficients.weight)


class DeCaL(BaseKGE):
    def __init__(self, args):
        super().__init__(args)
        self.name = 'DeCaL'
        self.entity_embeddings = torch.nn.Embedding(self.num_entities, self.embedding_dim)
        self.relation_embeddings = torch.nn.Embedding(self.num_relations, self.embedding_dim)
        self.p = self.args.get("p", 0)
        self.q = self.args.get("q", 0)
        self.r = self.args.get("r", 0)
        self.re = int(self.embedding_dim / (self.r + self.p + self.q + 1))

        # Initialize parameters for dimension scaling
        if self.p > 0:
            self.p_coefficients = torch.nn.Embedding(num_embeddings=1, embedding_dim=self.p)
            torch.nn.init.zeros_(self.p_coefficients.weight)
        if self.q > 0:
            self.q_coefficients = torch.nn.Embedding(num_embeddings=1, embedding_dim=self.q)
            torch.nn.init.zeros_(self.q_coefficients.weight)
        if self.r > 0:
            self.r_coefficients = torch.nn.Embedding(num_embeddings=1, embedding_dim=self.r)
            torch.nn.init.zeros_(self.r_coefficients.weight)

    def forward_triples(self, x: torch.Tensor) -> torch.FloatTensor:
        """

        Parameter
        ---------
        x: torch.LongTensor with (n, ) shape

        Returns
        -------
        torch.FloatTensor with (n) shape
        """
        # (1) Retrieve real-valued embedding vectors.
        head_ent_emb, rel_ent_emb, tail_ent_emb = self.get_triple_representation(x)
        # (2) Construct multi-vector in Cl_{p,q,r} (\mathbb{R}^d) for head entities and relations
        h0, hp, hq, hk = self.construct_cl_multivector(head_ent_emb, re=self.re, p=self.p, q=self.q, r=self.r)
        r0, rp, rq, rk = self.construct_cl_multivector(rel_ent_emb, re=self.re, p=self.p, q=self.q, r=self.r)
        t0, tp, tq, tk = self.construct_cl_multivector(tail_ent_emb, re=self.re, p=self.p, q=self.q, r=self.r)

        # h0, hp, hq, hk, h0, rp, rq, rk = self.apply_coefficients(h0, hp, hq, hk, h0, rp, rq,rk)

        # (4) Compute a triple score based on interactions described by the basis 1. 
        h0r0t0 = torch.einsum('br, br -> b', h0 * r0, t0)

        # (5) Compute a triple score based on interactions described by the bases of p {e_1, ..., e_p}.
        if self.p > 0:
            # Second term in Eq.16
            hp_rp_t0 = torch.einsum('brp, br  -> b', hp * rp, t0)
            # Eq. 17
            # b=e
            h0_rp_tp = torch.einsum('brp, erp -> b', torch.einsum('br,  brp -> brp', h0, rp), tp)
            hp_r0_tp = torch.einsum('brp, erp -> b', torch.einsum('brp, br  -> brp', hp, r0), tp)

            score_p = hp_rp_t0 + h0_rp_tp + hp_r0_tp
        else:
            score_p = 0

        # (5) Compute a triple score based on interactions described by the bases of q {e_{p+1}, ..., e_{p+q}}. Eq. 22
        if self.q > 0:
            # Third item in Eq 16.
            hq_rq_t0 = torch.einsum('brq, br  -> b', hq * rq, t0)
            # Eq. 18.
            h0_rq_tq = torch.einsum('br, brq  -> b', h0, rq * tq)
            r0_hq_tq = torch.einsum('br, brq  -> b', r0, hq * tq)
            score_q = - hq_rq_t0 + (h0_rq_tq + r0_hq_tq)
        else:
            score_q = 0

        if self.r > 0:
            # Eq. 18.
            h0_rk_tk = torch.einsum('br, brk  -> b', h0, rk * tk)
            r0_hk_tk = torch.einsum('br, brk  -> b', r0, hk * tk)
            score_r = (h0_rk_tk + r0_hk_tk)
        else:
            score_r = 0

        if self.p >= 2:
            sigma_pp = torch.sum(self.compute_sigma_pp(hp, rp), dim=[1, 2]).unsqueeze(-1)
        else:
            sigma_pp = 0

        if self.q >= 2:
            sigma_qq = torch.sum(self.compute_sigma_qq(hq, rq), dim=[1, 2]).unsqueeze(-1)
        else:
            sigma_qq = 0

        if self.r >= 2:
            sigma_rr = torch.sum(self.compute_sigma_qq(hk, rk), dim=[1, 2]).unsqueeze(-1)
        else:
            sigma_rr = 0

        if self.p >= 2 and self.q >= 2:
            sigma_pq = torch.sum(self.compute_sigma_pq(hp=hp, hq=hq, rp=rp, rq=rq), dim=[1, 2, 3]).unsqueeze(-1)
        else:
            sigma_pq = 0

        if self.p >= 2 and self.r >= 2:
            sigma_pr = torch.sum(self.compute_sigma_pq(hp=hp, hk=hk, rp=rp, rk=rk), dim=[1, 2, 3]).unsqueeze(-1)
        else:
            sigma_pr = 0
        if self.q >= 2 and self.r >= 2:
            sigma_qr = torch.sum(self.compute_sigma_pq(hq=hq, hk=hk, rq=rq, rk=rk), dim=[1, 2, 3]).unsqueeze(-1)
        else:
            sigma_qr = 0
        return h0r0t0 + score_p + score_q + score_r + sigma_pp + sigma_qq + sigma_rr + sigma_pq + sigma_qr + sigma_pr

    def cl_pqr(self, a:torch.tensor)->torch.tensor:

        ''' Input: tensor(batch_size, emb_dim) ---> output: tensor with 1+p+q+r components with size (batch_size, emb_dim/(1+p+q+r)) each.

        1) takes a tensor of size (batch_size, emb_dim), split it into 1 + p + q +r components, hence 1+p+q+r must be a divisor 
        of the emb_dim. 
        2) Return a list of the 1+p+q+r components vectors, each are tensors of size (batch_size, emb_dim/(1+p+q+r)) '''

        # num1 = 2**(p+q+r) #total number of vector in cl_pqr then after choose the first p+q+r+1 vectors
        num1 = 1 + self.p + self.q + self.r
        a1 = torch.hsplit(a, num1)

        return torch.stack(a1)

    def compute_sigmas_single(self, list_h_emb, list_r_emb, list_t_emb):

        '''here we compute all the sums with no others vectors interaction taken with the scalar product with t, that is,
        
        .. math::

             s0 = h_0r_0t_0
             s1 = \sum_{i=1}^{p}h_ir_it_0
             s2 = \sum_{j=p+1}^{p+q}h_jr_jt_0
             s3 = \sum_{i=1}^{q}(h_0r_it_i + h_ir_0t_i)
             s4 = \sum_{i=p+1}^{p+q}(h_0r_it_i + h_ir_0t_i)
             s5 = \sum_{i=p+q+1}^{p+q+r}(h_0r_it_i + h_ir_0t_i)
        
        and return:
        
        .. math::

            sigma_0t = \sigma_0 \cdot t_0 = s0 + s1 -s2
            s3, s4 and s5
        
        
        '''

        p = self.p
        q = self.q
        r = self.r

        h_0 = list_h_emb[0]  # h_i = list_h_emb[i] similarly for r and t
        r_0 = list_r_emb[0]
        t_0 = list_t_emb[0]

        s0 = (h_0 * r_0 * t_0).sum(dim=1)

        s1 = (t_0 * (list_h_emb[1:p + 1] * list_r_emb[1:p + 1])).sum(dim=[-1, 0])

        s2 = (t_0 * (list_h_emb[p + 1:p + q + 1] * list_r_emb[p + 1:p + q + 1])).sum(dim=[-1, 0])

        s3 = (h_0 * (list_r_emb[1:p + 1] * list_t_emb[1:p + 1]) + r_0 * (
                    list_h_emb[1:p + 1] * list_t_emb[1:p + 1])).sum(dim=[-1, 0])

        s4 = (h_0 * (list_r_emb[p + 1:p + q + 1] * list_t_emb[p + 1:p + q + 1]) + r_0 * (
                    list_h_emb[p + 1:p + q + 1] * list_t_emb[p + 1:p + q + 1])).sum(dim=[-1, 0])

        s5 = (h_0 * (list_r_emb[p + q + 1:p + q + r + 1] * list_t_emb[p + q + 1:p + q + r + 1]) + r_0 * (
                    list_h_emb[p + q + 1:p + q + r + 1] * list_t_emb[p + q + 1:p + q + r + 1])).sum(dim=[-1, 0])

        sigma_0t = s0 + s1 - s2

        return sigma_0t, s3, s4, s5

    def compute_sigmas_multivect(self, list_h_emb, list_r_emb):

        '''Here we compute and return all the sums with vectors interaction for the same and different bases.

           For same bases vectors interaction we have

           .. math::

                \sigma_pp = \sum_{i=1}^{p-1}\sum_{i'=i+1}^{p}(h_ir_{i'}-h_{i'}r_i) (models the interactions between e_i and e_i' for 1 <= i, i' <= p)
                \sigma_qq = \sum_{j=p+1}^{p+q-1}\sum_{j'=j+1}^{p+q}(h_jr_{j'}-h_{j'} (models the interactions between e_j and e_j' for p+1 <= j, j' <= p+q)
                \sigma_rr = \sum_{k=p+q+1}^{p+q+r-1}\sum_{k'=k+1}^{p}(h_kr_{k'}-h_{k'}r_k) (models the interactions between e_k and e_k' for p+q+1 <= k, k' <= p+q+r) 
            
           For different base vector interactions, we have
           
            .. math::

                \sigma_pq = \sum_{i=1}^{p}\sum_{j=p+1}^{p+q}(h_ir_j - h_jr_i) (interactionsn between e_i and e_j for 1<=i <=p and p+1<= j <= p+q)
                \sigma_pr = \sum_{i=1}^{p}\sum_{k=p+q+1}^{p+q+r}(h_ir_k - h_kr_i) (interactionsn between e_i and e_k for 1<=i <=p and p+q+1<= k <= p+q+r)
                \sigma_qr = \sum_{j=p+1}^{p+q}\sum_{j=p+q+1}^{p+q+r}(h_jr_k - h_kr_j) (interactionsn between e_j and e_k for p+1 <= j <=p+q and p+q+1<= j <= p+q+r)
           
           '''

        p = self.p
        q = self.q
        r = self.r

        if p > 0:
            indices_i = torch.arange(1, p)
            sigma_pp = ((list_h_emb[indices_i] * list_r_emb[indices_i + 1].sum(dim=0)) - (
                        list_h_emb[indices_i + 1].sum(dim=0) * list_r_emb[indices_i])).sum(dim=[-1, 0])
        else:
            indices_i = []
            sigma_pp = 0
        if q > 0:
            indices_j = torch.arange(p + 1, p + q)
            sigma_qq = ((list_h_emb[indices_j] * list_r_emb[indices_j + 1].sum(dim=0)) - (
                        list_h_emb[indices_j + 1].sum(dim=0) * list_r_emb[indices_j])).sum(dim=[-1, 0])
        else:
            indices_j = []
            sigma_qq = 0
        if r > 0:
            indices_k = torch.arange(p + q + 1, p + q + r)
            sigma_rr = ((list_h_emb[indices_k] * list_r_emb[indices_k + 1].sum(dim=0)) - (
                        list_h_emb[indices_k + 1].sum(dim=0) * list_r_emb[indices_k])).sum(dim=[-1, 0])
        else:
            indices_k = []
            sigma_rr = 0

        sigma_pq = ((list_h_emb[indices_i] * list_r_emb[indices_j].sum(dim=0)) - (
                    list_h_emb[indices_j].sum(dim=0) * list_r_emb[indices_i])).sum(dim=[-1, 0])
        sigma_pr = ((list_h_emb[indices_i] * list_r_emb[indices_k].sum(dim=0)) - (
                    list_h_emb[indices_k].sum(dim=0) * list_r_emb[indices_i])).sum(dim=[-1, 0])
        sigma_qr = ((list_h_emb[indices_j] * list_r_emb[indices_k].sum(dim=0)) - (
                    list_h_emb[indices_k].sum(dim=0) * list_r_emb[indices_j])).sum(dim=[-1, 0])

        return sigma_pp, sigma_qq, sigma_rr, sigma_pq, sigma_pr, sigma_qr

    def forward_k_vs_all(self, x: torch.Tensor) -> torch.FloatTensor:

        """
            Kvsall training

            (1) Retrieve real-valued embedding vectors for heads and relations
            (2) Construct head entity and relation embeddings according to Cl_{p,q, r}(\mathbb{R}^d) .
            (3) Perform Cl multiplication
            (4) Inner product of (3) and all entity embeddings

            forward_k_vs_with_explicit and this funcitons are identical
            Parameter
            ---------
            x: torch.LongTensor with (n, ) shape
            Returns
            -------
            torch.FloatTensor with (n, |E|) shape
            """
        # (1) Retrieve real-valued embedding vectors.
        head_ent_emb, rel_ent_emb = self.get_head_relation_representation(x)
        # (2) Construct multi-vector in Cl_{p,q} (\mathbb{R}^d) for head entities and relations
        h0, hp, hq, hk = self.construct_cl_multivector(head_ent_emb, re=self.re, p=self.p, q=self.q, r=self.r)
        r0, rp, rq, rk = self.construct_cl_multivector(rel_ent_emb, re=self.re, p=self.p, q=self.q, r=self.r)

        h0, hp, hq, hk, h0, rp, rq, rk = self.apply_coefficients(h0, hp, hq, hk, h0, rp, rq, rk)
        # (3) Extract all entity embeddings
        E = self.entity_embeddings.weight
        # (3.1) Extract real part
        t0 = E[:, :self.re]
        # (4) Compute a triple score based on interactions described by the basis 1.
        h0r0t0 = torch.einsum('br,er->be', h0 * r0, t0)

        # (5) Compute a triple score based on interactions described by the bases of p {e_1, ..., e_p}.
        if self.p > 0:
            tp = E[:, self.re: self.re + (self.re * self.p)].view(self.num_entities, self.re, self.p)
            hp_rp_t0 = torch.einsum('brp, er  -> be', hp * rp, t0)
            h0_rp_tp = torch.einsum('brp, erp -> be', torch.einsum('br,  brp -> brp', h0, rp), tp)
            hp_r0_tp = torch.einsum('brp, erp -> be', torch.einsum('brp, br  -> brp', hp, r0), tp)
            score_p = hp_rp_t0 + h0_rp_tp + hp_r0_tp
        else:
            score_p = 0

        # (5) Compute a triple score based on interactions described by the bases of q {e_{p+1}, ..., e_{p+q}}.
        if self.q > 0:
            num = self.re + (self.re * self.p)
            tq = E[:, num:num + (self.re * self.q)].view(self.num_entities, self.re, self.q)
            h0_rq_tq = torch.einsum('brq, erq -> be', torch.einsum('br,  brq -> brq', h0, rq), tq)
            hq_r0_tq = torch.einsum('brq, erq -> be', torch.einsum('brq, br  -> brq', hq, r0), tq)
            hq_rq_t0 = torch.einsum('brq, er  -> be', hq * rq, t0)
            score_q = h0_rq_tq + hq_r0_tq - hq_rq_t0
        else:
            score_q = 0

        # (6) Compute a triple score based on interactions described by the bases of q {e_{p+q+1}, ..., e_{p+q+r}}.
        if self.r > 0:
            tk = E[:, -(self.re * self.r):].view(self.num_entities, self.re, self.r)
            h0_rk_tk = torch.einsum('brk, erk -> be', torch.einsum('br,  brk -> brk', h0, rk), tk)
            hk_r0_tk = torch.einsum('brk, erk -> be', torch.einsum('brk, br  -> brk', hk, r0), tk)
            # hq_rq_t0 = torch.einsum('brq, er  -> be', hq * rq, t0)
            score_r = h0_rk_tk + hk_r0_tk
        else:
            score_r = 0

        if self.p >= 2:
            sigma_pp = torch.sum(self.compute_sigma_pp(hp, rp), dim=[1, 2]).unsqueeze(-1)
        else:
            sigma_pp = 0

        if self.q >= 2:
            sigma_qq = torch.sum(self.compute_sigma_qq(hq, rq), dim=[1, 2]).unsqueeze(-1)
        else:
            sigma_qq = 0

        if self.r >= 2:
            sigma_rr = torch.sum(self.compute_sigma_rr(hk, rk), dim=[1, 2]).unsqueeze(-1)
        else:
            sigma_rr = 0

        if self.p >= 2 and self.q >= 2:
            sigma_pq = torch.sum(self.compute_sigma_pq(hp=hp, hq=hq, rp=rp, rq=rq), dim=[1, 2, 3]).unsqueeze(-1)
        else:
            sigma_pq = 0
        if self.p >= 2 and self.r >= 2:
            sigma_pr = torch.sum(self.compute_sigma_pr(hp=hp, hk=hk, rp=rp, rk=rk), dim=[1, 2, 3]).unsqueeze(-1)
        else:
            sigma_pr = 0
        if self.q >= 2 and self.r >= 2:
            sigma_qr = torch.sum(self.compute_sigma_qr(hq=hq, hk=hk, rq=rq, rk=rk), dim=[1, 2, 3]).unsqueeze(-1)
        else:
            sigma_qr = 0

        return h0r0t0 + score_p + score_q + score_r + sigma_pp + sigma_qq + sigma_rr + sigma_pq + sigma_pr + sigma_qr

    def apply_coefficients(self, h0, hp, hq, hk, r0, rp, rq, rk):
        """ Multiplying a base vector with its scalar coefficient """
        if self.p > 0:
            hp = hp * self.p_coefficients.weight
            rp = rp * self.p_coefficients.weight
        if self.q > 0:
            hq = hq * self.q_coefficients.weight
            rq = rq * self.q_coefficients.weight
        if self.r > 0:
            hk = hk * self.r_coefficients.weight
            rk = rk * self.r_coefficients.weight
        return h0, hp, hq, hk, r0, rp, rq, rk

    def construct_cl_multivector(self, x: torch.FloatTensor, re: int, p: int, q: int, r: int) -> tuple[
        torch.FloatTensor, torch.FloatTensor, torch.FloatTensor]:
        """
        Construct a batch of multivectors Cl_{p,q,r}(\mathbb{R}^d)

        Parameter
        ---------
        x: torch.FloatTensor with (n,d) shape

        Returns
        -------
        a0: torch.FloatTensor 
        ap: torch.FloatTensor 
        aq: torch.FloatTensor 
        ar: torch.FloatTensor 
        """
        batch_size, d = x.shape
        # (1) A_{n \times k}: take the first k columns
        a0 = x[:, :re].view(batch_size, re)
        # (2) B_{n \times p}, C_{n \times q}: take the self.k * self.p columns after the k. column
        if p > 0:
            ap = x[:, re: re + (re * p)].view(batch_size, re, p)
        else:
            ap = torch.zeros((batch_size, re, p), device=self.device)
        if q > 0:
            # (3) B_{n \times p}, C_{n \times q}: take the last self.r * self.q .
            aq = x[:, re + (re * p):re + (re * p) + (re * q):].view(batch_size, re, q)
        else:
            aq = torch.zeros((batch_size, re, q), device=self.device)
        if r > 0:
            # (3) B_{n \times p}, C_{n \times q}: take the last self.r * self.q .
            ar = x[:, -(re * r):].view(batch_size, re, r)
        else:
            ar = torch.zeros((batch_size, re, r), device=self.device)
        return a0, ap, aq, ar

    def compute_sigma_pp(self, hp, rp):
        """
        Compute 
        .. math::
        
            \sigma_{p,p}^* = \sum_{i=1}^{p-1}\sum_{i'=i+1}^{p}(x_iy_{i'}-x_{i'}y_i)

        \sigma_{pp} captures the interactions between along p bases
        For instance, let p e_1, e_2, e_3, we compute interactions between e_1 e_2, e_1 e_3 , and e_2 e_3
        This can be implemented with a nested two for loops

                        results = []
                        for i in range(p - 1):
                            for k in range(i + 1, p):
                                results.append(hp[:, :, i] * rp[:, :, k] - hp[:, :, k] * rp[:, :, i])
                        sigma_pp = torch.stack(results, dim=2)
                        assert sigma_pp.shape == (b, r, int((p * (p - 1)) / 2))

        Yet, this computation would be quite inefficient. Instead, we compute interactions along all p,
        e.g., e1e1, e1e2, e1e3,
              e2e1, e2e2, e2e3,
              e3e1, e3e2, e3e3
        Then select the triangular matrix without diagonals: e1e2, e1e3, e2e3.
        """
        # Compute indexes for the upper triangle of p by p matrix
        indices = torch.triu_indices(self.p, self.p, offset=1)
        # Compute p by p operations
        sigma_pp = torch.einsum('nrp,nrx->nrpx', hp, rp) - torch.einsum('nrx,nrp->nrpx', hp, rp)
        sigma_pp = sigma_pp[:, :, indices[0], indices[1]]
        return sigma_pp

    def compute_sigma_qq(self, hq, rq):
        """
        Compute  

        .. math::
        
            \sigma_{q,q}^* = \sum_{j=p+1}^{p+q-1}\sum_{j'=j+1}^{p+q}(x_jy_{j'}-x_{j'}y_j) Eq. 16

        sigma_{q} captures the interactions between along q bases
        For instance, let q e_1, e_2, e_3, we compute interactions between e_1 e_2, e_1 e_3 , and e_2 e_3
        This can be implemented with a nested two for loops

                        results = []
                        for j in range(q - 1):
                            for k in range(j + 1, q):
                                results.append(hq[:, :, j] * rq[:, :, k] - hq[:, :, k] * rq[:, :, j])
                        sigma_qq = torch.stack(results, dim=2)
                        assert sigma_qq.shape == (b, r, int((q * (q - 1)) / 2))

        Yet, this computation would be quite inefficient. Instead, we compute interactions along all p,
        e.g., e1e1, e1e2, e1e3,
              e2e1, e2e2, e2e3,
              e3e1, e3e2, e3e3
        Then select the triangular matrix without diagonals: e1e2, e1e3, e2e3.
        """
        # Compute indexes for the upper triangle of p by p matrix
        if self.q > 1:
            indices = torch.triu_indices(self.q, self.q, offset=1)
            # Compute p by p operations
            sigma_qq = torch.einsum('nrp,nrx->nrpx', hq, rq) - torch.einsum('nrx,nrp->nrpx', hq, rq)
            sigma_qq = sigma_qq[:, :, indices[0], indices[1]]

        else:
            sigma_qq = torch.zeros((len(hq), self.re, int((self.q * (self.q - 1)) / 2)))

        return sigma_qq

    def compute_sigma_rr(self, hk, rk):
        """
        .. math:: 
        
            \sigma_{r,r}^* = \sum_{k=p+q+1}^{p+q+r-1}\sum_{k'=k+1}^{p}(x_ky_{k'}-x_{k'}y_k)

        """
        # Compute indexes for the upper triangle of p by p matrix
        if self.r > 1:
            indices = torch.triu_indices(self.r, self.r, offset=1)
            # Compute p by p operations
            sigma_rr = torch.einsum('nrp,nrx->nrpx', hk, rk) - torch.einsum('nrx,nrp->nrpx', hk, rk)
            sigma_rr = sigma_rr[:, :, indices[0], indices[1]]
        else:
            sigma_rr = torch.zeros((len(hk), self.re, int((self.r * (self.r - 1)) / 2)))

        return sigma_rr

    def compute_sigma_pq(self, *, hp, hq, rp, rq):
        """
        Compute 

        .. math:: 
        
            \sum_{i=1}^{p} \sum_{j=p+1}^{p+q} (h_i r_j - h_j r_i) e_i e_j

        results = []
        sigma_pq = torch.zeros(b, r, p, q)
        for i in range(p):
            for j in range(q):
                sigma_pq[:, :, i, j] = hp[:, :, i] * rq[:, :, j] - hq[:, :, j] * rp[:, :, i]
        print(sigma_pq.shape)

        """
        sigma_pq = torch.einsum('nrp,nrq->nrpq', hp, rq) - torch.einsum('nrq,nrp->nrpq', hq, rp)
        assert sigma_pq.shape[1:] == (self.re, self.p, self.q)
        return sigma_pq

    def compute_sigma_pr(self, *, hp, hk, rp, rk):
        """
        Compute

        .. math:: 

            \sum_{i=1}^{p} \sum_{j=p+1}^{p+q} (h_i r_j - h_j r_i) e_i e_j

        results = []
        sigma_pq = torch.zeros(b, r, p, q)
        for i in range(p):
            for j in range(q):
                sigma_pq[:, :, i, j] = hp[:, :, i] * rq[:, :, j] - hq[:, :, j] * rp[:, :, i]
        print(sigma_pq.shape)

        """
        sigma_pr = torch.einsum('nrp,nrk->nrpk', hp, rk) - torch.einsum('nrk,nrp->nrpk', hk, rp)
        assert sigma_pr.shape[1:] == (self.re, self.p, self.r)
        return sigma_pr

    def compute_sigma_qr(self, *, hq, hk, rq, rk):
        """
        .. math:: 

            \sum_{i=1}^{p} \sum_{j=p+1}^{p+q} (h_i r_j - h_j r_i) e_i e_j

        results = []
        sigma_pq = torch.zeros(b, r, p, q)
        for i in range(p):
            for j in range(q):
                sigma_pq[:, :, i, j] = hp[:, :, i] * rq[:, :, j] - hq[:, :, j] * rp[:, :, i]
        print(sigma_pq.shape)

        """
        sigma_qr = torch.einsum('nrq,nrk->nrqk', hq, rk) - torch.einsum('nrk,nrq->nrqk', hk, rq)
        assert sigma_qr.shape[1:] == (self.re, self.q, self.r)
        return sigma_qr
