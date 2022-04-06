import torch
from .base_model import *
import numpy as np
from .static_funcs import quaternion_mul


class AdaptE(BaseKGE):
    """ AdaptE: A linear combination of DistMult, ComplEx and QMult """

    def __init__(self, args):
        super().__init__(args)
        self.name = 'AdaptE'
        try:
            assert self.embedding_dim % 4 == 0
        except AssertionError:
            print('AdaptE embedding size must be dividable by 4')
        self.entity_embeddings = nn.Embedding(self.num_entities, self.embedding_dim)
        self.relation_embeddings = nn.Embedding(self.num_relations, self.embedding_dim)
        xavier_normal_(self.entity_embeddings.weight.data), xavier_normal_(self.relation_embeddings.weight.data)

        self.input_dp_ent_real = torch.nn.Dropout(self.input_dropout_rate)
        self.input_dp_rel_real = torch.nn.Dropout(self.input_dropout_rate)

        self.normalize_head_entity_embeddings = self.normalizer_class(self.embedding_dim)
        self.normalize_relation_embeddings = self.normalizer_class(self.embedding_dim)
        self.normalize_tail_entity_embeddings = self.normalizer_class(self.embedding_dim)

        self.losses = []
        # If the current loss is not better than 60% of the previous interval loss
        # Upgrade.
        self.moving_average_interval = 10
        self.decision_criterion = .8
        self.mode = 0
        self.moving_average = 0

    def forward_triples(self, indexed_triple: torch.Tensor) -> torch.Tensor:
        """

        e1_idx: torch.Tensor
        rel_idx: torch.Tensor
        e2_idx: torch.Tensor
        :return:
        """
        # (1) Retrieve embeddings & Apply Dropout & Normalization
        head_ent_emb, rel_ent_emb, tail_ent_emb = self.get_triple_representation(indexed_triple)
        # (2) Compute DistMult score on (1)
        score = self.compute_real_score(head_ent_emb, rel_ent_emb, tail_ent_emb)
        if self.mode >= 1:
            # (3) Compute ComplEx score on (1).
            # (3.1) Add (3) to (2)
            score += self.compute_complex_score(head_ent_emb, rel_ent_emb, tail_ent_emb)
        if self.mode >= 2:
            # (4) Compute QMult score on (1)
            # (4.1) Add (4) to (2)
            score += self.compute_quaternion_score(head_ent_emb, rel_ent_emb, tail_ent_emb)

        # (5) Average (2)
        if self.mode == 0:
            return score
        elif self.mode == 1:
            return score / 2
        elif self.mode == 2:
            return score / 3
        else:
            raise KeyError

    def forward_k_vs_all(self, x: torch.Tensor) -> torch.Tensor:
        e1_idx: torch.Tensor
        rel_idx: torch.Tensor
        e2_idx: torch.Tensor
        e1_idx, rel_idx, e2_idx = x[:, 0], x[:, 1], x[:, 2]
        raise NotImplementedError()
        head_ent_emb = self.norm_ent(self.emb_ent_real(e1_idx))
        rel_ent_emb = self.norm_rel(self.emb_rel_real(rel_idx))
        # (1) real value.
        score = torch.mm(head_ent_emb * rel_ent_emb, self.emb_ent_real.weight.transpose(1, 0))
        # if self.mode >= 1:
        emb_head_real, emb_head_imag = torch.hsplit(head_ent_emb, 2)
        emb_rel_real, emb_rel_imag = torch.hsplit(rel_ent_emb, 2)
        emb_all_entity_real, emb_all_entity_imag = torch.hsplit(self.emb_ent_real.weight, 2)

        real_real_real = torch.mm(emb_head_real * emb_rel_realemb_all_entity_real.transpose(1, 0))
        real_imag_imag = torch.mm(emb_head_real * emb_rel_i, emb_all_entity_imag.transpose(1, 0))
        imag_real_imag = torch.mm(emb_head_i * emb_rel_real, emb_all_entity_imag.transpose(1, 0))
        imag_imag_real = torch.mm(emb_head_i * emb_rel_i, emb_all_entity_real.transpose(1, 0))

        score += real_real_real + real_imag_imag + imag_real_imag - imag_imag_real
        return score / 3

    def training_epoch_end(self, training_step_outputs):
        # (1) Store Epoch Loss.
        epoch_loss = float(training_step_outputs[0]['loss'].detach())
        self.losses.append(epoch_loss)
        # (2) Check whether we have enough epoch losses to compute moving average.
        if len(self.losses) % self.moving_average_interval == 0:
            # (2.1) Compute the average loss of epoch losses.
            avg_loss_in_last_epochs = sum(self.losses) / len(self.losses)
            # (2.2) Is the current epoch loss less than the current moving average of losses.
            tendency_of_decreasing_loss = avg_loss_in_last_epochs > epoch_loss
            # (2.3) Remove the oldest epoch loss saved.
            self.losses.pop(0)
            # (2.4) Check whether the moving average of epoch losses tends to decrease
            if tendency_of_decreasing_loss:
                """ The loss is decreasing """
            else:
                # (2.5) Stagnation detected.
                self.losses.clear()
                if self.mode == 0:
                    print('\nIncrease the mode to complex numbers')
                    self.mode += 1
                elif self.mode == 1:
                    print('\nincrease the mode to quaternions numbers')
                    self.mode += 1
                else:
                    """ We may consider increasing the number of params"""

    @staticmethod
    def compute_real_score(head, relation, tail):
        return (head * relation * tail).sum(dim=1)

    @staticmethod
    def compute_complex_score(head, relation, tail):
        emb_head_real, emb_head_imag = torch.hsplit(head, 2)
        emb_rel_real, emb_rel_imag = torch.hsplit(relation, 2)
        emb_tail_real, emb_tail_imag = torch.hsplit(tail, 2)

        # (3) Compute hermitian inner product.
        real_real_real = (emb_head_real * emb_rel_real * emb_tail_real).sum(dim=1)
        real_imag_imag = (emb_head_real * emb_rel_imag * emb_tail_imag).sum(dim=1)
        imag_real_imag = (emb_head_imag * emb_rel_real * emb_tail_imag).sum(dim=1)
        imag_imag_real = (emb_head_imag * emb_rel_imag * emb_tail_real).sum(dim=1)
        return real_real_real + real_imag_imag + imag_real_imag - imag_imag_real

    @staticmethod
    def compute_quaternion_score(head, relation, tail):
        # (5) Split (1) into real and 3 imaginary parts.
        r_val, i_val, j_val, k_val = quaternion_mul(Q_1=torch.hsplit(head, 4), Q_2=torch.hsplit(relation, 4))
        emb_tail_real, emb_tail_i, emb_tail_j, emb_tail_k = torch.hsplit(tail, 4)
        real_score = (r_val * emb_tail_real).sum(dim=1)
        i_score = (i_val * emb_tail_i).sum(dim=1)
        j_score = (j_val * emb_tail_j).sum(dim=1)
        k_score = (k_val * emb_tail_k).sum(dim=1)
        return real_score + i_score + j_score + k_score