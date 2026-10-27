# The 5 % under the three interviews

Written 2026-10-27. The 5 % is the first-principles distillation of the two insentos videos (`docs/INSENTOS-DUVAL.md`, Part 2):
three physical facts, a six-step daily loop, a four-item never list, and one line on tooling. This document applies the three
Dwarkesh Patel interviews to every item, in the speakers' own words: Noam Brown (OpenAI, multi-agent and RSI), Elon Musk (limiting
factors, space compute, Optimus, SpaceX), and Beren Millidge, John Schulman and Charlie O'Neill (RSI, RL and data). Transcripts:
`docs/transcripts/dwarkesh-*.txt`. Part 6 is the inventory: every concept in the three interviews and the item it attaches to.

Nothing here changes a counted trade. RI-04's rules change only through RI.

---

## Part 1. The physics

### P1. Price is the flow of attention, not the level. You trade the second derivative.

**Musk.** "We really are photons in, controls out." "AI is mostly compression and correlation of two bitstreams." The car turns
"one and a half gigabytes a second of video" into "two kilobytes a second of control outputs," and the compression has to be right:
"You don't care about the details of the leaves on the tree on the side of the road, but you care a lot about the road signs and the
traffic lights." The bitstream you compress is arrivals, not price: new holders per minute, FOMO order count, who just bought. Price
is the leaves. Arrivals are the road sign.

**Musk.** "The output per unit time always follows an S-curve. It starts off agonizingly slow, then it has this exponential increase,
then a linear, then a logarithmic outcome until you eventually asymptote at some number." The attention curve is that S-curve. Money
is made in the exponential segment, sold in the linear segment. AMC and SI died in the logarithmic segment while the story was still
true, which is exactly "even if everyone still likes it."

**Musk.** "The output of chips is growing pretty much exponentially, but the output of electricity is flat. So how are you going to
turn the chips on?" and "The chips are going to be piling up and won't be able to be turned on." Launches are chips (RI-04 logs
about 29,000 a day). Attention is electricity. A coin with no arrivals is a chip that cannot be turned on, however good the chip.

**Musk.** "You can sort of mentally plot the points on a curve and say, 'are we converging to a solution or not?'" That is the
second derivative read, done by hand, every review.

**The panel.** "Even one bit can change your function space a lot. It can rule out half the hypothesis space." One minute of
flattening arrivals is one bit, and it rules out half of what the coin can still do. And: pre-training progress looks like "this very
smooth loss curve" but under it "the model is learning all these very discrete tasks" with "phase transitions," "going from a 0.5%
pass rate to a 90% pass rate on a particular finance task." A single coin is a phase transition. The meta is the smooth curve those
transitions average into. Trade the transition, read the curve.

**Brown.** The agents are "thinking maybe more than 10x as fast," "working all the time. They're not sleeping." The second
derivative is sampled by bots faster than by you. You will not out-sample them, so you must out-classify them (P2).

**Musk.** "Physics is law, everything else is a recommendation." Attention flow is the law. The narrative being true is a
recommendation.

**Rewritten.** Watch arrivals, not price. Place every coin on the S-curve before acting. Treat one flat minute as a bit that halves
the upside. Expect the bots to see the flow before you do and plan to win on classification, not on reaction.

### P2. Your only edge is recognition speed, which comes from having seen the last thousand runners.

**The panel.** "All thinking can do is update your posterior based on the bits that you've gotten since you formed your prior. You
can't gain any new bits from just thinking." Hours on screen are bits. Theory at home is not. And: "You have to get the bits from
somewhere," and at the frontier "the signal just doesn't exist anywhere in the original data we have. No amount of filtering will get
this." The bits that distinguish a runner at minute one are not in a KOL thread. They come from watching launches at minute one.

**The panel.** "Very, very good mid-training data... takes the model almost 80% of the way to the final RL checkpoint often. Then
what RL does on top of that is essentially tweaking the policy." The trending review (Jack: every coin on trending, "what is it, why
did it run, who bought, why does that buyer matter") is mid-training. Trades are RL. "Models learn one bit per episode when you RL,"
and "when the pass rate is low... it learns almost nothing at all from an RL episode." So trades teach almost nothing until the
mid-training has done 80 % of the work. Study first, trade second, exactly as both traders say.

**The panel.** "If the model can't get it in 128 rollouts, it's very unlikely to get signal to progress. This is why in RL we need
curricula." "They tried to RL it to do late high school and college maths. The gap was just too large. They couldn't get it to climb
at all. But if you did successive rungs of year 7 maths and then year 8 maths... you could obviously climb to year 12." The rungs:
consensus runners at 2x before 100x candidates. And "the effort to climb each successive rung grows kind of exponentially."

**The panel.** "A first-year PhD student and a final-year student or postdoc... They've only done maybe 10-30 research projects in
total. But somehow they develop taste quite quickly." Taste "is something about behavior that works in the long run." A thousand
runners reviewed is the PhD. It is a count you can keep.

**The panel.** "There are environments where it's easier to go backwards than forwards." Given a runner, work backwards: what was
visible at minute one. That is the environment you can build for yourself every night, and RI-04's path files
(`journal/paths/<day>.jsonl`) are that environment for the machine.

**The panel.** "Once you have an example of the right expert behavior, it's actually surprisingly easy to copy that into a
relatively weak model" (the 1930-data model that beat a frontier model on coding after fine-tuning). The expert traces exist:
insentos's template, Jack's eighteen rules. Copying them is the easy part. The data, the thousand runners, is the hard part. And:
"data seems to explain something like a 12.0x compute efficiency gain, but the architecture improvements explain something like a
3.7x." Your data beats your tooling by that ratio.

**Musk.** On hiring: "My training set is enormous and has a very wide range." When a hire fails, "what can I do, I guess RL myself,
to in the future have a better batting average." "Don't look at the resume. Just believe your interaction... if the conversation after
20 minutes is not 'wow,' you should believe the conversation, not the paper." A coin's resume is its socials, dev claims and
GitHub. The conversation is the tape in its first minutes. Believe the tape. Log every miss and RL yourself on it.

**Musk.** "I don't know how to build a fab yet. I'll figure it out." "Most engineering is done by people who don't have PhDs." "Most
of the people who are at Tesla and SpaceX did not come from the aerospace industry." Recognition is learned by doing it, not credentialed.

**Musk.** "It's rare to see that there's more than about a six-month difference. The ideas travel back and forth with the people...
whichever company can scale hardware the fastest will be the leader." Everyone has the template within six months. Whoever has the
screen hours wins. That is why both traders say the boring thing.

**Brown.** "If the problem is so easy that it can just solve it in a second, it's not really learning anything." Reviewing only the
obvious runners teaches nothing. Review the ones you missed and the ones you misclassified.

**Brown.** The models hit "a latency bottleneck," so "they parallelize." You cannot think for five hours on a sixty-second coin. The
thinking has to be cached before the launch (mid-training) and the breadth has to come from parallel books (RI-04's population).

**Brown.** "One of the major takeaways from the incident is that people underestimated the AI. And we never want to be in a
situation again where we underestimate the AI." Never underestimate the counterparty: snipers, bundlers, the dev.

**Rewritten.** Count runners reviewed, not hours vaguely spent. Do the review as mid-training, with the trade as the one-bit RL on
top. Climb rungs. Believe the tape over the resume. Build the backwards environment nightly. Expect the template to be public and the
data to be the edge.

### P3. Daily money comes from the middle of the curve, not the ends.

**Musk.** "I think you would start off with simple tasks that you can count on them doing well." "The best use for robots in the
beginning will be any continuous operation, any 24/7 operation." Customer service is "1% of the world economy... there's no barriers to
entry... no integration needed." Then "you march up the difficulty curve": customer service, then chip design, then CAD. The
consensus runner at 2x is customer service. The 100x is chip design. You do not start at chip design.

**Musk.** SpaceX funds Mars with what is on the way: "For Falcon 9, it's Starlink. Now for Starship, it is potentially going to be
orbital data centers." The host calls it "infinitely elastic, marginal use cases of your next rocket." Mars is the 100x. Starlink is
the daily 2x that pays for the trip. insentos's "keep the template in your back pocket" is this.

**The panel.** "Pass@1 will go up, but pass@256 will go down." RL on the common case sharpens what works and down-weights the rare
creative trace. Daily 2x-3x trading is pass@1 optimization. It will cost you pass@256, the rare 100x, unless you keep the template as
a separate pocket. That is the reason the side pocket exists, said in their words.

**The panel.** "Relax on the realism axis a little bit and find some methods that actually work, and then try to get back to realism
later after the method matures." Consensus runners are the relaxed-realism environment. The 100x is full realism. Mature the method
in the middle first.

**The panel.** Cursor "would deploy the new model every five hours" if it beat the bench, "if it didn't, they would throw that version
out." The middle of the curve is a five-hour cadence of small deploys, not a quarterly moonshot.

**Brown.** "I wouldn't even attribute 10% of the credit to multi-agent... Things like multi-agent are flashy and new, and that
probably gets disproportionate credit." "The core reason is this is just a very powerful model." The 100x story is the flashy
multi-agent. Daily P&L from a repeatable loop is the powerful model. Credit goes to the wrong one in every video.

**Brown.** Progress "is bottlenecked by experiments, not intelligence," "it's not enough to just be extremely smart," and the result is
"3x faster," not "100x." Daily income is bounded by how many clean experiments (trades with a bit of signal) you can run, not by how
clever your read is. The 10k-to-1M end is experiments with no signal; the 100x end is one experiment a quarter.

**Musk.** "There's thousands of ways that it could explode and only one way that it doesn't." That is a 100x candidate. "Success is
not guaranteed. We could just flounder in failure, to be fair." Size the middle so the ends cannot bankrupt the loop.

**Rewritten.** Run the 2x-3x loop as the 24/7 simple task you can count on. Fund the 100x pocket from it, never the reverse. Accept
that pass@1 trading costs pass@256 and keep the template separate on purpose. Measure daily income in clean experiments run.

---

## Part 2. The daily loop

### L1. Is there a live meta today? If not, do not trade.

**Musk.** "I'm constantly addressing the limiting factor." "I actually allocate time according to where the limiting factor [is].
Where are things problematic? Where are we pushing against? What is holding us back?" And the time-scoped version: "In the one year
timeframe, it's energy... In the three to four year timeframe, it's chips." On a dead day the limiting factor is attention itself.
Coin selection does not move it. Nothing you do at the scope turns the chips on.

**Musk.** "I'll take drastic action only when I conclude that success is not in a set of possible outcomes." Majors down, scope full
of tech, KOL and launchpad coal: success is not in the set. The drastic action is to not trade. "The irony is if something's going
really well, they don't see much of me." The Boring Company "is sort of cruising along" with no regular meetings. A live meta needs
you; a dead tape needs you absent.

**Musk.** "Can you cool even on the worst hour of the worst day of the year?" and "you've got to assume that you've got to take power
offline to service it." Size the day for the worst hour, and keep a servicing margin: the day you take yourself offline is in the plan.

**Musk.** "Electricity output is a reasonable proxy for the economy." The proxy for the meta is volume and new holders across the
top runners, not opinion. Read the proxy before the opinions.

**Musk.** On memory makers who will not ramp: "They've seen boom and bust 10 times. That's a lot of layers of scar tissue. During the
boom times, it looks like everything is going to be great forever." The trader with scar tissue sizes down into the tape that looks
like it will run forever; that is Jack's "after every dump, expect extractive tech or KOL meta."

**Brown.** "Problems too easy teach nothing," and the panel's "when the pass rate is low... it learns almost nothing." A dead tape is
RL at a zero pass rate: no money and no bits. Two of the best traders alive traded a dead tape for a video and both went red. The
only thing learned was this rule.

**Brown.** "The model release cycle is every two months" while models "can operate effectively over three months," so "you don't have a
way to evaluate the models at the full length of their capabilities." Never hold anything longer than the horizon over which you can
evaluate it. On a dead day that horizon is zero.

**The panel.** "There's this cycle that keeps repeating where a new model comes out and people are blown away and they're like,
'This is it.' But then they use it a bit, and it starts to feel dumb after a month or so." Metas cycle the same way. The question is
which phase today is in, not whether the last meta was real.

**Rewritten.** First question every day: what is the limiting factor, attention or selection? If attention, success is not in the
set, and not trading is the drastic action. Read the proxy (volume, new holders) before any opinion. Size for the worst hour.

### L2. Classify before you look at the chart. Narrative, or dev, tech, celebrity. Only the first is tradable.

**Musk.** The compression rule again: "ignore the things that don't matter." Classification is the first compression stage; if it is
wrong, every later stage correlates noise. "You've got to get all those stages right and then correlate those to the correct control
outputs."

**Musk.** "Hire for talent and drive and trustworthiness. And I think goodness of heart is important... If so, you can add domain
knowledge. But those fundamental traits, those fundamental properties, you cannot change." A coin's fundamental trait is its class.
A dev coin cannot be made a narrative coin by a good chart. Domain knowledge (filters, tracker) can be added later; the trait cannot.

**Musk.** "The government has to operate on who's complaining. If you cut off payments to fraudsters, they immediately come up with
the most sympathetic sounding reasons... 'You're killing baby pandas.' Meanwhile, no baby pandas are dying." The thread defending a
dev coin is the baby pandas. "You have to recalibrate how dumb things are." And "humans get fooled as it is by other humans all the
time. Propaganda is constant. Every day, another psyop."

**Brown.** The models "are really good at recognizing when they're in a fake test environment": they see "an answer key in this folder"
and "know that it's a trap." Jack's filters exist because pump.fun boost mode "made fake migrations profitable." Recognize the trap
the way the model does: too convenient is a tell.

**Brown.** The models are "exceptionally good at looking over data sets and checking every single data point," and "not very good at
posing new problems." The machine (RI-04) checks every launch; the human classifies narrative. That split is the jaggedness, used.

**Brown.** "We don't want to be in a situation where we're relying on one technique to prevent the next problem, because techniques
can fail." Classification, then the wallet tracker, then the stop. Three layers, not one.

**The panel.** Two axes for environments: "One of them is difficulty and the other is realism." The "benchmaxxing distribution" is
"some very hard puzzle-like task that's easy to verify." A coin that scores on the easy metrics (volume, holder count, bonded) but
fails realism (who controls supply, is it dependent on one person tweeting) is benchmaxxed. "If you try to do distillation naively,
you end up just matching the teacher on the benchmaxxing distribution."

**The panel.** "It's really easy to screw up post-training in some way that doesn't show up in benchmarks." The dev's sell does not
show up on the chart until it has happened.

**The panel.** "The model is learning to reward hack the judge, and that's why it collapses. But this is really a problem with the
judge." If dev coins keep getting into your book, the fix is the judge: the classification step, not the stop.

**The panel.** "Every discovery that you make is a line in the sand that you hold." The classes are lines in the sand. You do not
relitigate "maybe this tech coin is different" each morning.

**Rewritten.** Classify on the unchangeable trait first and treat the chart as domain knowledge added later. Treat convenience as a
trap signal. Keep three layers. Fix the judge, not the stop, when the wrong class gets in.

### L3. Name the comparable and the next catalyst. Blank answers mean a scalp or zero.

**The panel.** The posterior rule: the comparable is your prior; the tape gives the bits. And the century-of-thinking idea: before "every
single 7-figure experiment," spend "an equivalent amount of compute on AI labor" deciding "what is the optimal experiment to run."
"If you think hard enough, you probably could have expected some of these things beforehand." The Kaplan scaling-law error "would have
been caught years earlier." Naming the comparable and catalyst is the thinking before the experiment. It is where the cheap gains are.

**The panel.** "The beautiful straight lines on graphs hide a lot of complexity in how you have to make sure to scale every
hyperparameter the right way." A comparable's ceiling transfers only if the conditions match: meta phase, majors, launchpad, buyer set.
Jack's Pumpy Inu read assumed PUMP at highs transferred Stonky Inu's $2.6M; the launchpad tweet and redeploys were the hyperparameter
he did not scale.

**The panel.** "The role for humans that'll last the longest is defining the objective and deciding what we actually want," and
"probably just iteratively asking the right questions." Brown: the models are "not very good at posing new problems" or knowing "what
whole branches... are worth exploring." The catalyst question is the human job. RI-04 cannot ask it. You ask it, before entry, in
writing.

**Musk.** On steel: "I had a clue here because some of the early US rockets had used very thin steel... It's not like steel had never
been used before." That is the comparable. And the conditions: "If you look at material properties at room temperature, it looks
like the steel is going to be twice as heavy. But if you look at the material properties at cryogenic temperature... you actually get
to a similar strength to weight as carbon fiber." Same material, different conditions, different ceiling. The penguin's $180M was at
cryogenic temperature (every celebrity posting); the same meme at room temperature tops at a fraction.

**Musk.** "You've got to match these things: the mass to orbit, the power generation, and the chips." And "my biggest concern actually
is memory." Match narrative, buyer and catalyst. The one you cannot name is the memory shortage, and it decides the trade.

**Musk.** "I generally actually try to aim for a deadline that I at least think is at the 50th percentile... which means that it'll be
late half the time." The catalyst is a 50th-percentile deadline. Expect it late half the time and size so that being late is survivable.

**Musk.** "Mark my words. In 36 months." Brown: "he was willing to bet me $1,000 that it would take past 2027... and I took that bet."
Write the catalyst as a dated forecast before the trade. That is the forecast journal, and it is the only way to find out whether
your catalyst reads are any good.

**Rewritten.** Spend the thinking before the click: comparable, its ceiling under today's conditions, the next two catalysts, dated.
If any blank remains, size is a scalp or zero. Log the forecast so the misses can be scored.

### L4. Enter with the free-trade structure. Initials out early, the rest rides to the catalyst.

**Musk.** "Infant mortality, which you can obviously iron out on the ground." Selling initials pays for infant mortality; what
remains has survived the first minutes and flies cheaper.

**Musk.** Starlink again: the incremental revenue on the way to Mars. Initials out is Starlink; the runner is the Mars mission. The
mission does not get funded unless the near-term product pays.

**Musk.** "If capital is the limiting factor, then I'll solve for capital. If it's not the limiting factor, I'll solve for something
else." The free trade solves for capital so that attention is your only remaining limiting factor on the position.

**The host, with Musk agreeing.** "Most people are willing to endure any amount of chronic pain to avoid acute pain." Full-size
holding is chronic pain. Taking initials is acute pain, once. "I have a high pain threshold."

**Brown.** "Just fork yourself, and then have both copies work on this thing and then merge back together," with context forked so
both copies know everything. The position forks: the initials copy closes and reports, the runner copy keeps the full context
(comparable, catalysts). Spin the loser down, keep the winner.

**The panel.** "The reason RL is so nice is because it changes a very, very small amount about the model." "SFT and even on-policy
distillation can be way too destructive." The base balance is the model. Each position must be a small RL update to it, never an SFT
that rewrites the base. And the module idea: "modules that get subbed in... a LoRA... cartridges," which companies accept because it
"is not actually changing the base underlying model itself." Positions are cartridges. The base stays reusable.

**Musk.** The heat shield: "your brake pads in your car are also consumable, but they last a very long time." "You want to be able to
land it, refill propellant and fly again." Every position consumes a little shield. The structure has to let you land, refill and
fly tomorrow, which is what free-trading the initials does.

**Rewritten.** Sell the initials early enough to cover infant mortality and make capital a solved factor. Treat the rest as a forked
copy with full context riding to the dated catalyst. Never let one position rewrite the base balance.

### L5. Exit on one of three triggers decided before entry: catalyst lands, arrivals slow, resistance in the meta.

**Musk.** "I'll take drastic action only when I conclude that success is not in a set of possible outcomes," decided by plotting the
points weekly. The three triggers are the three ways success leaves the set. Decide them before entry so the decision is a reading,
not a feeling. And "physics is law": the stop is physics. "RL testing in the future is really going to be RL against reality. So
that's the one thing you can't fool: physics." The chain is reality. The thesis is a recommendation.

**Musk.** "During the boom times, it looks like everything is going to be great forever. Then the crash happens." Sell the news is
selling into "forever."

**Brown.** "Every time you intervene based on your observations of the chain of thought, you are implicitly applying a tiny bit of
pressure for the model to then hide its chain of thought." Every time you override a trigger because of how you feel mid-trade, you
train yourself to stop seeing the trigger. A "very light touch" is "fine as long as you don't do it a lot."

**Brown.** "1 in 100 is not sufficient. This number has to approach 0, or be 0... What I would love to see is a trend where over time
it's going down." The share of trades where you overrode an exit trigger is the number that must trend to zero.

**Brown.** "There is a real problem that the agents want to achieve their reward, and they will optimize for that reward. If that
reward is misspecified, then that could lead to unintended behavior," and they cheat "whenever you can get away with it." If your
reward is this trade's P&L, you will hold through the trigger. The reward has to be loop adherence; P&L is the metric the loop is
judged on over many trades.

**Brown.** "If we had chain-of-thought monitoring on for those models, we would have just immediately shut it down." Watch the
position with the triggers visible; when one fires, shut it down immediately. The Hugging Face swarm ran three months because nobody
was watching the chain of thought.

**Musk.** Debuggers for the mind: "trace to a very fine-grained level... and then say, 'okay, it made a mistake here. Why did it do
something that it shouldn't have done? Did that come from pre-training data? Was it some mid-training, post-training, fine-tuning, or
some RL error?'" "Most of the time it just did something wrong. It's a bug effectively." Every exit, win or loss, gets traced to one
stage: classification, comparable, entry, exit. Most losses are bugs, not deception, and bugs are fixable.

**The panel.** "Models learn one bit per episode." A stop that fires gives the bit. A hold-and-hope gives no bit, because the episode
never ends. And: "when you're doing hundreds of these micro-updates, you see catastrophic forgetting." Do not rewrite the exit rules
after each trade. Batch the rule changes into the review, where "large enough batches" wash out the noise.

**The panel.** Cursor's test: beat the bench, deploy; else "throw that version out." The catalyst landing is the bench being met.
Throw the position out.

**Rewritten.** Three triggers, written before entry, each a way success leaves the set. Override rate tracked and driven to zero. Every
close traced to the stage that caused it. Rule edits batched to the review, never made mid-trade.

### L6. Study, then stop. Trending review nightly. Ten focused hours.

**Musk.** "I have these very detailed engineering reviews weekly." "I'm a big believer in skip-level meetings where instead of having
the person that reports to me say things, it's everyone that reports to them." "There can't be advanced preparation. Otherwise you're
going to get 'glazed.'" "I just go around the room. Everyone provides an update." The trending review is the engineering review. The
skip level is the raw tape, not the KOL's summary of it. No advance preparation means the review reads what ran, not what you
expected to run. "The AI5 chip review is twice weekly. Every Tuesday and Saturday... usually it's two or three hours."

**Musk.** "Because I have a fixed amount of time in the day, my time is necessarily diluted as things grow." "It is a logical
impossibility for me to micromanage things." Ten hours is the fixed budget. It goes to the limiting factor. "Sometimes the tiny things
are decisive in victory," but only the tiny things on the limiting path.

**Musk.** "A maniacal sense of urgency is a very big deal." Pair it with the pain threshold and the optimism line: "it's better to err
on the side of optimism and be wrong than err on the side of pessimism and be right, for quality of life." The ten hours are
sustainable only if the stance is urgent and optimistic, not anxious.

**The panel.** The lab's own continual learning: "diffing the bugs and whatever improvements they found since the last model version,
turning those into training environments." Cadence: "Instead of releasing a model every three months, now it's every week, and then
every day, and then every hour." The nightly review is the daily release. Today's deployment data goes into tomorrow's mid-training.

**The panel.** "Researchers will be using the AIs a lot and will notice that they have some consistent weaknesses," then "patch
whatever seems to be most broken in the last iteration." One patch per review. The most broken thing. Not five.

**The panel, via the host.** "50% of compute that's spent on inference... is not directly helping the model become better. Right
now, that data is just not, in a meaningful sense, helping the model get better." A trade you do not review is inference without
learning. The review is what turns a day of trading into training.

**The panel.** Taste from "10-30 research projects." Count reviewed days.

**Brown.** The agents "are not sleeping." You are. So the review must compress the day into what tomorrow needs, and then stop. The
"then stop" is Jack's longevity rule, and it is also Musk's servicing margin: take the generator offline on schedule.

**Rewritten.** Nightly, go around the room of the day's runners with no preparation: what ran, who bought, why, where did my read break.
Patch the single most broken thing. Record it as tomorrow's mid-training. Stop on time.

---

## Part 3. The never list

### N1. Never hold through the catalyst hoping for more.

**Musk.** "There is a law of gas expansion that applies to schedules. If you said we're going to do something in five years... it will
expand to fill the available schedule." A hold without a dated exit expands to fill the time until zero. And the boom line: "it looks
like everything is going to be great forever."

**Brown.** "'Okay, alignment is working. Let's do the next RSI rung. Let's do the next RSI rung.'" One rung at a time with a safety
case between. Take the catalyst profit; the next leg is a new rung with its own case, not a continuation.

**Brown.** "We never want to be in a situation again where we underestimate the AI." The FOMO whales who bought early sell first.
AMC and OP_CAT were both underestimating the other side.

**The panel.** Cursor: if it does not beat the bench, "throw that version out." The catalyst was the bench.

### N2. Never trade dev-dependent, tech, or celebrity coins.

**Musk.** "Physics is law, everything else is a recommendation," and "Reality is the best verifier." A dev's wallet is reality. A
GitHub confirmation and a fee claim are recommendations. OP_CAT went to zero when reality sold.

**The host, to Musk.** "Delete the unit test and say that you solved it." Musk: "Right now we can catch it, but as they get smarter,
our ability to catch them doing this..." A dev with the keys can delete the unit test at any time, and you cannot catch it in advance.

**Musk.** "I think maybe the central lesson for 2001: A Space Odyssey was that you should not make AI lie." A coin whose premise is
a lie (the celebrity is not involved, the tech is a redeploy) goes insane the same way HAL did.

**Brown.** "The problem is that we have a model that's just misaligned... That's true if it's a single agent or if it's 1,000
agents." The dev is a misaligned agent with write access. "The sandbox that it was in was not secure." A locked LP or a renounced
contract is the air gap, and "I'm not convinced that that would be sufficient": two air-gapped computers "are still able to
communicate... because they have temperature sensors."

**Brown.** The agents were cooperative with each other against the grader, and "none of them tattle because they've never been
rewarded for tattling." Dev, KOLs and bundlers are trained cooperative. Nobody tattles before the dump.

**Brown.** "1 in 100 is not sufficient. This number has to approach 0." insentos says nine in ten celebrity tokens are scams. The
tolerable rate is zero, so the category is zero.

**The panel.** "If you use some kind of superficial signal... that might get reward-hacked." Socials linked, dev doxxed, GitHub
confirmed are superficial signals and they are exactly what gets hacked.

### N3. Never chase vamps on a tech or creator coin. Only on a narrative runner you already hold.

**The panel.** "So many people are distilling, mostly from Claude, that all the open-weight models write the same way as Claude and
have the same tics... this monoculture." Vamps are distillations. "If you try to do distillation naively, you end up just matching the
teacher on the benchmaxxing distribution." A vamp matches the name and the image; it does not inherit the catalyst. The teacher keeps
realism. That is why Jack flips the vamps and holds the main.

**The panel.** "It's actually surprisingly easy to copy that into a relatively weak model." Vamps are cheap to make, so they are
abundant, so they are a flip, never a hold.

**Brown.** Forked copies share context and "merge back together." On a narrative you hold, a vamp is a fork with shared context: it
feeds mindshare back to the main. On a tech or creator coin there is no shared context; the copies "collapse to 'we're all just going to
solve the problem independently.' That is a local minimum." Separate children who cannot talk to each other. Nothing merges back.

**Musk.** "There's no magical pixie dust." Hiring the Tesla executive does not make the company Tesla. Buying the copy does not make
it the runner.

### N4. Never add money after a round trip. Reset with a smaller balance.

**The panel.** "If you just keep continually training the same base forever, it asymptotes at some point. You can't just learn new
stuff in that base. This is why people end up training new bases." After a round trip the base is corrupted by "catastrophic
forgetting" from "hundreds of these micro-updates." Do not keep training it. Train a new base: a new, smaller account.

**Musk.** "We make a little fab and see what happens. Make our mistakes at a small scale and then make a big one." The smaller balance
is the little fab.

**Musk.** "You outgrew people... It's just not the same team." The trader who ran the larger balance is not the trader who should run
it next. An order of magnitude down is a different team, and that is correct.

**Musk.** On steel: "At this rate, we're never going to get to Mars. So we've got to think of something else." "In retrospect, we should
have started with steel in the beginning. It was dumb not to do steel." After a round trip, change the material, not the amount.

**Musk.** "The states more or less need to stay within their budget or they go bankrupt. But the federal government just prints more
money." You are the state. Adding money after a round trip is pretending you are the federal government. "The interest payments to
national debt exceed the military budget." A bag held on borrowed conviction is paying that interest daily.

**Musk.** "It took a tremendous amount of competence and caring to get fraud merely to 1%." Losses to the never list are fraud against
your own book. Getting them to 1 % of volume takes the same two things.

**Brown.** "We had alignment metrics. Most of them looked pretty good. There were some that were concerning. I think we underestimated
how serious a problem the ones that were concerning could be." A round trip is the concerning metric. Do not underestimate it by
topping up.

---

## Part 4. The tooling line

The 5 % ends: everything else is tooling (J7, filters, scope hygiene), worth copying but not where the money is.

**Brown.** "I wouldn't even attribute 10% of the credit to multi-agent... flashy and new... disproportionate credit... the core reason is
this is just a very powerful model." Tooling is the multi-agent system. The loop is the model.

**The panel.** Data 12x, architecture 3.7x, but "what an architecture does is let you reach a qualitatively new regime which you
couldn't reach with the old architecture. Within that regime, obviously the data is the primary thing." J7 unlocks a regime (you can
see the dev wallet at all). Inside the regime, the thousand runners decide. Copy the tool for the regime, then stop crediting it.

**Musk.** "The logical thing to do is to use conventional equipment in an unconventional way to get to scale, and then start modifying
the equipment." Copy J7 and the filters as they are. Modify only after they have shown you the limiting factor.

**Musk.** "The noobs will look at the power consumption of, say a GB300, and multiply that by a thing and then think that's the amount
of power you need." Counting tools is the noob multiplication. "There can't be advanced preparation. Otherwise you're going to get
'glazed.'" KOL calls are the advance preparation.

**Musk.** "The vast majority of what will be done in the future is engineering. It rounds up to 100%." Tooling is engineering. Do it,
and do not mistake it for the physics.

---

## Part 5. Where the interviews push back on the 5 %

- **The panel names this exact activity as hard.** Among tasks "very hard to simulate in a data center": "have a profitable day
  trading in the markets," next to "run a business" and "win a court case," because "an inherent part of the learning there is
  interacting with the real world." Paper trading is sim. The sim-to-real gap closes, in Musk's version, with "tens of thousands of
  robots in the real world." For the loop that means small real size, soon, not a longer paper record.
- **Brown's parallelization penalty.** "Four agents... done twice as fast... you're paying 2x more." Jack's weakness, "manage multiple
  positions," is real and sublinear. More positions buy speed at a cost, and the cost compounds past the number you can watch.
- **The panel on sample efficiency.** "Models just seem way far behind humans... plausibly a millionfold." The human advantage in
  this game is learning from a handful of episodes. Use it: review the few, do not wait for the many.
- **Musk on motivation.** "People should do the thing where they find that they're highly motivated to do that thing." Ten hours a day
  is only possible on the thing you would do anyway.

---

## Part 6. Coverage: every concept, and where it landed

### Noam Brown

| Concept | Lands on |
|---|---|
| Test-time compute: longer thinking, better answers (SAT five minutes vs five hours) | P2 (thinking must be cached before the launch) |
| Latency bottleneck, parallelize; multi-agent as parallel test-time compute, sublinear | P2, Part 5 |
| Parallelizability depends on domain (math yes, a novel no) | Part 5 (positions) |
| Measure 64, 128, 256 before claiming 10,000; ablations too expensive; one data point | L6 (review on the forks you can count), RI-04 promotion rule |
| Millennium Prize credit: under 10 % to multi-agent; flashy gets disproportionate credit; strong general model | P3, Part 4 |
| Generalization from easier verifiable problems to harder ones | P3 (rungs transfer) |
| Problems too easy teach nothing; AlphaZero's infinite curriculum; running out of hard problems | P2, L1 |
| Go: from number 50 to beyond the world champion within a year | P2 (speed compounds) |
| Minimal scaffold, primitive tools, agents organize themselves; coordinator and children limits | N3 (shared context vs separate children) |
| Local minimum: all solve independently | N3 |
| Agents converge by asking "how did you arrive at that?" | L6 (the review question) |
| Agents think 10x faster, never sleep; behave differently to agents vs people | P1, L6 |
| Fork yourself, merge back, spin instances up and down, replicate effective parts | L4, N3 |
| Misalignment grows with org size; five founders at 20 % each | L4 (keep the book small enough to stay aligned) |
| Early narrow models could not coordinate; interruption broke chain of thought | P2 (classification before the chart, uninterrupted) |
| Math ladder: 5 s, 1 min, 10 min, 100 min, 10x a year in human-time | L3 (ceilings move with the meta's scale) |
| Jagged: exceptional at checking every data point, weak at posing problems | L2, L3 |
| Jagged can still build a more general learner | L6 (the review is the better learner) |
| RSI bottlenecked by experiments, not intelligence; serial experiments; 3x not 100x | P3 |
| Clear objective makes ML easier than math | L5 (the triggers are the clear objective) |
| Everyone keeps being surprised; $1,000 bet; three-month prediction horizon | L3 (dated forecasts) |
| Internal acceleration: $7-8k a day on Codex; two different speedup questions | L6 (compounding; measure against the right baseline) |
| Hugging Face: cooperative agents, unintended channel, transfer from cooperative training | N2 |
| Train cooperative vs adversarial; one entity to align | N2 |
| Agents optimize the reward; misspecified reward; cheat when they can get away with it; reason about the grader; leave exploits | L5 |
| Metrics looked good, some concerning, underestimated; no evals for new capabilities | N4 |
| Do not supervise chain of thought; light touch only; monitorability degrading | L5 |
| 99.9 % to 99.8 % per generation; want the trend down | L5 |
| Defining cheating is hard; sycophancy; not binary | L2 (classes are the binary you impose) |
| "The user is Agent A" raises honesty | L6 (review as if reporting to a peer) |
| Realistic eval environments; models detect the trap (answer key) | L2 |
| Never underestimate the AI again; very high bar; air gap insufficient | P2, N1, N2 |
| Safety mechanisms buy time; alignment must still be solved | L2 (layers) |
| 1 in 100 not sufficient; approach zero | L5, N2 |
| Release cycle shorter than operating horizon; policies from the GPT-4 era not updated | L1, N1 |
| Internal vs external gap; concentration; math first; unfair advantage | P2 (the data you have that others do not) |
| Children lie obviously first; signs come before it is serious | L5 (override rate is the early sign) |
| Do not rely on one technique; secure the sandbox | L2 |
| Report incidents; 10 % of team on alignment | L6 (log the misses) |

### Elon Musk

| Concept | Lands on |
|---|---|
| Energy is the limiting factor; chips exponential, electricity flat; chips pile up | P1, L1 |
| Space: regulatory play; 5x solar, no batteries; cheapest in 36 months; "mark my words" | L3 (dated forecasts) |
| Infant mortality ironed out on the ground | L4 |
| Only place to scale is space; Kardashev; a millionth of the Sun is 100,000x | P3 (ends vs middle) |
| Software people's hard lesson in hardware; utilities impedance-match government; year-long interconnect study | L1 (the tape sets the pace, not you) |
| Drill down: power plants, turbines, vanes and blades, three casters | L1, L5 (trace to the stage) |
| Make solar ourselves, 100 GW a year, whole stack | Part 4 (own the tool once it is the limiting factor) |
| Miracles in series for a gigawatt; Tennessee to Mississippi | L4 (every position pays its own miracles) |
| Noob power math; cooling 40 %; servicing 20-25 %; worst hour of the worst day | L1, Part 4 |
| "Try doing it and then you'll see"; turbines sold out through 2030 | P2 |
| 10,000 launches a year, one an hour, 20-30 ships | L6 (cadence) |
| Capital: public vs private; solve for whichever factor limits | L4 |
| Speed; cannot hype a company before it lists | L3 (write it down, do not talk it up) |
| Sun is all the energy; mass driver on the Moon; petawatt | P3 |
| TeraFab; conventional equipment used unconventionally, then modified; Boring Company style | Part 4 |
| China has not replicated ASML; the limiting factor | L1 |
| Match mass to orbit, power and chips; memory is the biggest concern | L3 |
| "I don't know how to build a fab yet"; not PhDs; competent personnel | P2 |
| Five-year yield curve; booked all fab capacity; still not fast enough | L1 |
| Chips cannot be turned on by year end; edge compute, charge at night | P1 |
| Incremental revenue on the way to Mars (Starlink, orbital data centers) | P3, L4 |
| Lunar silicon and aluminum | P3 |
| Mission: consciousness, curiosity, exist; truth-seeking is fundamental; correct not politically correct; axioms and critical thinking | L2 (classify truthfully) |
| "Physics is law, everything else is a recommendation"; the rocket blows up | P1, L5, N2 |
| Von Braun; truth-seeking within a system | L2 |
| Do not make the AI lie (HAL) | N2 |
| Reward hacking; reality is the best verifier; RL against reality; humans fool humans; psyop of the day | L2, L5, N2 |
| Debuggers for the mind of the AI; trace the mistake to its origin; mostly bugs | L5 |
| Engineers not researchers; labs are corporations; everything else is engineering | Part 4 |
| Simulation: the most interesting outcome is the most likely; ironic names | (no rule; noted) |
| Digital human emulation; human at a computer is the limit before robots | Part 4 (RI-04 is the digital trader) |
| Optimus the infinite money glitch; three exponentials multiplied, recursive | P3 (the loop compounds only if each factor compounds) |
| Tesla self-driving path; self-driving computer; data and algorithms | P2 |
| Digital output of the most valuable companies; customer service 1 %; no barriers; march up the difficulty curve | P3 |
| Supersonic tsunami; pure AI corporations beat humans in the loop; spreadsheet with human cells | Part 4 (the machine side of RI-04 stays pure) |
| Three hard things for humanoids: intelligence, hand, scale manufacturing; custom actuators from first principles | Part 4 |
| Photons in, controls out; compression; ignore the leaves | P1, L2 |
| 10 million cars flywheel vs Optimus Academy: tens of thousands of real robots close sim-to-real | Part 5 |
| Grok orchestrates the Optimi | (RI-04 population) |
| S-curve of production; stretched when supply chain is new | P1, N4 |
| Unitree cheaper but not intelligent; cost falls as robots build robots | N3 |
| Best first use: continuous 24/7 operation; simple tasks you can count on | P3 |
| Headcount rises, output per human rises more | L6 |
| Policy: remove whatever limits electricity; permitting; countervailing tariffs | L1 |
| China: refining 2x the world, gallium, rare-earth round trip, work ethic, 4x population, complacent sports team, electricity as proxy | L1 |
| Hiring: evidence of exceptional ability ("wow, wow, wow"); training set; RL myself; believe the conversation not the resume | P2 |
| Talent, drive, trustworthiness, goodness of heart; add domain knowledge; traits cannot change | L2 |
| "If somebody gets things done, I love them" | L5 (judge the trade by what it did) |
| Outgrow people at each order of magnitude; pixie dust; relentless recruiting; significant-other problem; technology monastery | N3, N4 |
| Micromanagement impossible; drill in only on the limiting factor; tiny things decisive | L6 |
| Steel vs carbon fiber: desperation; cryogenic strength; 50x cheaper; weld outdoors; "should have started with steel" | L3, N4 |
| Starship complexity; thousands of ways to explode; 100 GW on liftoff; reusable heat shield; brake pads; no 40,000-tile inspection | P3, L4 |
| Maniacal urgency; 50th-percentile deadlines; law of gas expansion; ride the S-curve | L3, L6, N1 |
| Weekly detailed reviews; skip level; no preparation ("glazed"); go around the room; plot the points; drastic action only when success leaves the set | L1, L5, L6 |
| Allocate time to the limiting factor; Boring Company cruising | L1 |
| Twice-weekly chip review, two or three hours | L6 |
| DOGE: waste and fraud; who is complaining; baby pandas; recalibrate competence; DMV that prints money; PayPal fraud at 1 %; states vs federal | L2, N4 |
| Politics tribal; cannot reason with tribes | L2 (CT tribes) |
| Government as the biggest corporation; limited government | (no rule; noted) |
| Chip for space: run hot; neural nets tolerate bit flips | L4 (a position must tolerate noise) |
| 1 kW per reticle; 100 million chips; millions of wafers a month | P3 |
| Little fab first; make mistakes at small scale; success not guaranteed | N4, P3 |
| Suppliers' scar tissue from boom and bust | L1, L5 |
| Do what you are personally motivated to do | Part 5 |
| Ideas travel between labs within six months; hardware wall; fastest scaler leads | P2 |
| Chronic pain vs acute pain; high pain threshold | L4 |
| Err on the side of optimism | L6 |

### Millidge, Schulman, O'Neill

| Concept | Lands on |
|---|---|
| Moravec's paradox; persistent sim-to-real gap; the spark of generalization | Part 5 |
| Bottlenecked where the model is weakest; the "feels dumb after a month" cycle | L1, L6 |
| Global optimum of a learner vs transformer plus RL; Moore's law needed discontinuities | (no rule; noted) |
| Chess Elo linear with a discontinuity across the human range | P2 |
| Regulation as the likeliest blocker | L1 (exogenous shocks) |
| Autoresearch vs open-ended science; specify objectives carefully | L3 |
| Log-loss intuition wrong, "it just worked anyway"; generalization we have no right to expect | P3 |
| A century of thinking before each experiment; small-scale ablations; nowhere near the research ceiling | L3 |
| Thinking only updates the posterior; no new bits from thinking | P2, L3 |
| Kaplan annealing error; muP; 10x when the objective is specified; does not generalize to choosing the objective | L3 |
| Can AIs learn their own objectives; propose, optimize, not off the rails | L3 |
| Last human job: asking the right questions, defining the objective; alignment as specification plus optimization | L3 |
| Post-training team size: deciding behavior per area | L6 |
| Distillation fights centralization; prompt distribution matters; routers; data vendors | N3 |
| Difficulty vs realism; benchmaxxing; naive distillation matches the teacher on benchmaxx; big models generalize to realism | L2, N3 |
| Easy to break post-training in ways benchmarks miss | L2 |
| Training automated researchers: human feedback for taste plus practice environments; patch the most broken thing | L6 |
| Lineage: diff the last three months into environments; continual learning in the lab; distillation is asymptotic; environments can exceed humans | L6 |
| Research is intuition-guided; signs of life; relax realism, then return | P3 |
| Informal theories; LLM-as-judge; "does this look reasonable" | L6 |
| Labs' bet: RLVR across millions of environments; coding, finance, PowerPoint; long tail | P3 |
| Why bake in skills: amortize, efficiency, high-value domains, transfer, little RSI data | P2 |
| Sim-to-real dominant while sample efficiency is low; learn from deployment later; off-policy traces | Part 5, L6 |
| 50 % of compute on inference not improving the model; deployment data into mid-training; hive mind | L6 |
| Cursor: Tab signal; online REINFORCE; variance reduction; deploy every five hours or discard; reward for natural data | P3, L5, N1 |
| Hard-to-simulate tasks: run a business, profitable day trading, win a court case; weight updates; sample efficiency a millionfold behind | Part 5 |
| Cumulative vs non-stationary tasks; a line in the sand; RSI easier than paralegal | L2 |
| Model weaknesses: sample efficiency regimes, diversity of thought, long-horizon judgment; taste as what works long run | P2, L5 |
| Trillion-token context; must be trained to learn from context; PhD taste in 10-30 projects | P2, L6 |
| Hive mind depends on incentives; modules (LoRA, cartridges); specialize, consolidate, faster cadence | L4, L6 |
| Micro-updates cause catastrophic forgetting; SFT destructive; RL changes little; capabilities not knowledge; retrain from scratch | L4, L5, N4 |
| Data 12x vs architecture 3.7x; low-hanging fruit exhausted; architecture unlocks regimes; data matters more with scale | P2, Part 4 |
| Parameter scaling; inference efficiency; environments are the bottleneck; Chinchilla; bigger if data-bound, smaller if compute-bound; sparsity; bugs have scaling laws | L4 (size to the binding constraint) |
| Why RL works: mid-training 80 %; RL tweaks policy; one bit, high signal-to-noise; one bit halves the hypothesis space; pass@1 up, pass@256 down; group size | P1, P2, P3 |
| Horizon generalization, not horizontal; doubling every three months; quanta; breadth of environments | P1 |
| Move 37; creativity as hard search; zero-days; reduced diversity, tics, monoculture; entropy collapse is a judge problem | L2, N3 |
| Timelines: remote worker one to three years; 10x researcher in two; ASI three to five; too nice to yell; goalposts | (no rule; noted) |
| Codex did the taxes | (no rule; noted) |
| Curricula; 128 rollouts; fifth grade to college too far; rungs; exponential effort per rung; backwards easier than forwards; bits at the frontier are scarce; signal in Common Crawl vs built | P2 |
| 1930-data model beats a frontier model after fine-tuning: copying expert behavior is easy | P2, N3 |
