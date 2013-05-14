from django.core.management.base import BaseCommand, CommandError

from state_gov_tracker_app.models import PaBills, LegisVotes, PaLegisVotes
from django.conf import settings
from sunlight import openstates

###
# originally based on
# gather_recent_votes.py:
# Filename: find_leg_homepages.py
# Author:   Christopher M. Brown
# Project:  State Gov Track
# Task:     Uses openstates API to find legislator homepages
#
# Moved to django management command by Adam Hinz
###
class Command(BaseCommand):
    args = '<two-digit state abbr>'
    help = 'Update most recent bills for a given state'

    def handle(self, *args, **options):
        if len(settings.STATE_FILTER) != 2:
            raise CommandError('Expected two digit state prefix')

        state = settings.STATE_FILTER

        self.update_bills(state)
        self.update_votes(state)

    def votes_for_bill(self, bill):
        return openstates.bill_detail(bill_id=bill.bill_id, state=bill.state, session=bill.session)['votes']

    def update_votes(self, state):
        all_votes = []
        downloaded_votes = set([v.vote_id for v in LegisVotes.objects.all()])
        for bill in PaBills.objects.all():
            bill_id = bill.bill_id
            for vote in self.votes_for_bill(bill):
                vote_instance = LegisVotes(bill_id=bill, vote_id=vote['vote_id'],
                                           chamber=vote['chamber'], date=vote['date'],
                                           motion=vote['motion'], num_no=vote['no_count'],
                                           num_yes=vote['yes_count'],
                                           num_other=vote['other_count'], status=vote['passed'],
                                           type=vote['type'], session=vote['session'])

                vote_instance.save()

                vote_id = vote['vote_id']
                if vote_id not in downloaded_votes:
                    # Delete all previous legislative votes
                    PaLegisVotes.objects.filter(bill_id=bill, vote_id=vote_id).delete()
                    def mk_vote(vote_type, v):
                        if v['leg_id']:
                            PaLegisVotes(legid=v['leg_id'],
                                         bill_id=bill,
                                         vote=vote_type, date=vote_instance.date,
                                         vote_id=vote_instance).save()

                    for yes_vote in vote['yes_votes']:
                        mk_vote(1, yes_vote)

                    for no_vote in vote['no_votes']:
                        mk_vote(0, no_vote)

                    for other_vote in vote['other_votes']:
                        mk_vote(99, other_vote)

    def update_bills(self, state):
        prev_bills = [b.bill_id for b in PaBills.objects.all()]
        bills = openstates.bills(state=state, search_window="term")

        count = 0
        for bill in bills:
            if bill['bill_id'] not in prev_bills:
                count += 1
                new_bill = PaBills(state=state, session=bill['session'],
                                   title=bill['title'], type=bill['type'][0],
                                   chamber=bill['chamber'],
                                   created_at=bill['created_at'],
                                   updated_at=bill['updated_at'],
                                   bill_id=bill['bill_id'])
                new_bill.save()

        print "Added a total of %s bills to database" % count
