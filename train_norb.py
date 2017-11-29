"""
License: Apache-2.0
Author: Suofei Zhang, Hang Yu
E-mail: zhangsuofei at njupt.edu.cn
"""

import tensorflow as tf
import tensorflow.contrib.slim as slim
from config import cfg
from utils import create_inputs_norb
import time
import numpy as np
import os
import capsnet_em as net


def main(_):
    coord_add = [[[8., 8.], [12., 8.], [16., 8.], [24., 8.]],
                 [[8., 12.], [12., 12.], [16., 12.], [24., 12.]],
                 [[8., 16.], [12., 16.], [16., 16.], [24., 16.]],
                 [[8., 24.], [12., 24.], [16., 24.], [24., 24.]]]

    coord_add = np.array(coord_add, dtype=np.float32) / 32.

    with tf.Graph().as_default(), tf.device('/cpu:0'):

        summaries = []

        global_step = tf.get_variable(
            'global_step', [], initializer=tf.constant_initializer(0), trainable=False)

        num_batches_per_epoch = int(24300 * 2 / cfg.batch_size)

        """Use exponential decay leanring rate?"""
        lrn_rate = tf.maximum(tf.train.exponential_decay(1e-3, global_step, 2e2, 0.66), 1e-5)
        summaries.append(tf.summary.scalar('learning_rate', lrn_rate))

        opt = tf.train.AdamOptimizer(lrn_rate)

        batch_x, batch_labels = create_inputs_norb(is_train=True, epochs=cfg.epoch)
        # batch_y = tf.one_hot(batch_labels, depth=5, axis=1, dtype=tf.float32)

        m_op = tf.placeholder(dtype=tf.float32, shape=())
        with tf.device('/gpu:0'):
            with slim.arg_scope([slim.variable], device='/cpu:0'):
                assert cfg.num_classes == 5, "Please change num_classes in config.py to be 5."
                output = net.build_arch(batch_x, coord_add, is_train=True,
                                        num_classes=cfg.num_classes)
                # loss = net.cross_ent_loss(output, batch_labels)
                loss = net.spread_loss(output, batch_labels, m_op)

            grad = opt.compute_gradients(loss)

        summaries.append(tf.summary.scalar('spread_loss', loss))

        train_op = opt.apply_gradients(grad, global_step=global_step)

        sess = tf.Session(config=tf.ConfigProto(
            allow_soft_placement=True, log_device_placement=False))
        sess.run(tf.local_variables_initializer())
        sess.run(tf.global_variables_initializer())

        saver = tf.train.Saver(tf.global_variables(), max_to_keep=cfg.epoch)

        # read snapshot
        # latest = os.path.join(cfg.logdir, 'model.ckpt-4680')
        # saver.restore(sess, latest)

        # coord = tf.train.Coordinator()
        summary_op = tf.summary.merge(summaries)
        threads = tf.train.start_queue_runners(sess=sess, coord=None)

        summary_writer = tf.summary.FileWriter(cfg.logdir, graph=sess.graph)

        m = 0.2
        m_min = m
        m_max = 0.9
        for step in range(cfg.epoch * num_batches_per_epoch):

            tic = time.time()
            _, loss_value = sess.run([train_op, loss], feed_dict={m_op: m})
            print('%d iteration finishs in ' % step + '%f second' %
                  (time.time() - tic) + ' loss=%f' % loss_value)
            # test1_v = sess.run(test2)

            # if np.isnan(loss_value):
            #     print('bbb')
            #  assert not np.isnan(np.any(test2_v[0])), 'a is nan'
            assert not np.isnan(loss_value), 'loss is nan'

            if step % 10 == 0:
                summary_str = sess.run(summary_op, feed_dict={m_op: m})
                summary_writer.add_summary(summary_str, step)

            if (step % num_batches_per_epoch) == 0:
                if step > 0:
                    m += (m_max - m_min) / (cfg.epoch * 0.6)
                    if m > m_max:
                        m = m_max

                ckpt_path = os.path.join(cfg.logdir, 'model.ckpt')
                saver.save(sess, ckpt_path, global_step=step)

        # coord.join(threads)


if __name__ == "__main__":
    tf.app.run()
