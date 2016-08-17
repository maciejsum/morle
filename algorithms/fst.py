import libhfst
import shared
import sys

def seq_to_transducer(alignment, weight=0.0, type=None, alphabet=None):
    if type is None:
        type=shared.config['FST'].getint('transducer_type')
    tr = libhfst.HfstBasicTransducer()
    if alphabet is None:
        alphabet = ()
    alphabet = tuple(sorted(set(alphabet) | set(sum(alignment, ()))))
    tr.add_symbols_to_alphabet(alphabet)
    last_state_id = 0
    for (x, y) in alignment:
        state_id = tr.add_state()
#        tr.add_transition(state_id, libhfst.HfstBasicTransition(state_id, libhfst.EPSILON, libhfst.EPSILON, 0.0))
        if (x, y) == (libhfst.IDENTITY, libhfst.IDENTITY):
            tr.add_transition(last_state_id, 
                              libhfst.HfstBasicTransition(state_id,
                                                          libhfst.IDENTITY,
                                                          libhfst.IDENTITY,
                                                          0.0))
            tr.add_transition(state_id, 
                              libhfst.HfstBasicTransition(state_id,
                                                          libhfst.IDENTITY,
                                                          libhfst.IDENTITY,
                                                          0.0))
            for a in tr.get_alphabet():
                if not a.startswith('@_'):
                    tr.add_transition(last_state_id, libhfst.HfstBasicTransition(state_id, a, a, 0.0))
                    tr.add_transition(state_id, libhfst.HfstBasicTransition(state_id, a, a, 0.0))
        else:
            tr.add_transition(last_state_id, 
                              libhfst.HfstBasicTransition(state_id, x, y, 0.0))
        last_state_id = state_id
    tr.set_final_weight(last_state_id, weight)
    return libhfst.HfstTransducer(tr, type)

def binary_disjunct(transducers):
    stack, sizes = [], []
#    print('starting')
    count = 0
    while True:
        if len(sizes) >= 2 and sizes[-1] == sizes[-2]:
            first, first_size = stack.pop(), sizes.pop()
            second, second_size = stack.pop(), sizes.pop()
            first.disjunct(second)
#            if len(first.extract_paths()) <= 1:
#                print(second.extract_paths())
#                raise Exception('zonk')
            stack.append(first)
            sizes.append(first_size + second_size)
            stack[-1].minimize()
        else:
#            print('expand')
            try:
                stack.append(next(transducers))
                sizes.append(1)
                count += 1
#                sys.stdout.write('\r'+str(count))
#                sys.stdout.flush()
            except StopIteration:
                break
#    print()
#    print('final disjunction')
    t = stack.pop()
    while stack:
        t.disjunct(stack.pop())
#        if len(t.extract_paths()) <= 1:
#            raise Exception('zonk')
#    print('postprocessing')
    t.determinize()
    t.minimize()
    t.push_weights(libhfst.TO_INITIAL_STATE)
#    print('adding epsilon loops and word boundaries')
    t = libhfst.HfstBasicTransducer(t)
#    add_epsilon_loops(t)
#    add_word_boundaries(t)
    tr_type=shared.config['FST'].getint('transducer_type')
    return libhfst.HfstTransducer(t, tr_type)

A_TO_Z = tuple('abcdefghijklmnoprstuvwxyz')

def generate_id(id_num):
    result = A_TO_Z[id_num % len(A_TO_Z)]
    while id_num > len(A_TO_Z):
        id_num //= len(A_TO_Z)
        result = A_TO_Z[id_num % len(A_TO_Z)-1] + result
    return result

#def id_absorber(id_num):
#    seq = ('$',) + tuple(generate_id(id_num))
#    return seq_to_transducer(\
#        zip(seq, (libhfst.EPSILON,)*len(seq)),\
#        alphabet=A_TO_Z + ('$',))

def id_generator():
    tr = libhfst.HfstBasicTransducer()
    tr.add_symbols_to_alphabet(A_TO_Z + ('$',))
    tr.add_transition(0, 
                      libhfst.HfstBasicTransition(1, '$', '$', 0.0))
    for c in A_TO_Z:
        tr.add_transition(1, 
                          libhfst.HfstBasicTransition(1, c, c, 0.0))
    tr.set_final_weight(1, 0.0)
    return libhfst.HfstTransducer(tr, settings.TRANSDUCER_TYPE)

def number_of_paths(transducer):
    t = libhfst.HfstBasicTransducer(transducer)
    paths_for_state = [1] + [0] * (len(t.states())-1)
    result = 0
    changed = True
    while changed:
        changed = False
        new_paths_for_state = [0] * len(t.states())
        for state in t.states():
            if paths_for_state[state] > 0:
                for tr in t.transitions(state):
                    new_paths_for_state[tr.get_target_state()] +=\
                        paths_for_state[state]
                    changed = True
        for state in t.states():
            if t.is_final_state(state):
                result += new_paths_for_state[state]
        paths_for_state = new_paths_for_state
    return result


