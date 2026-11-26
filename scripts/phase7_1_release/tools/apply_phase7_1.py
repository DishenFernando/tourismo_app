#!/usr/bin/env python3
"""Tourismo Phase 7.1 changes-only installer.

Dry-run by default. Run in repository root after database backup:
    python tools/apply_phase7_1.py --check
    python tools/apply_phase7_1.py --apply

Does not touch .env, Docker Compose, existing DB data, or legacy migrations.
"""
import argparse
import ast
import difflib
from pathlib import Path
import shutil
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'new'
REPO = Path.cwd()
sys.path.insert(0, str(ROOT / 'tools'))
from routes_replacements import REPLACEMENTS


def replace_ast_nodes(original: str, replacements: dict[str,str]) -> str:
    tree = ast.parse(original)
    lines = original.splitlines(keepends=True)
    edits = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in replacements:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])-1
            edits.append((start, node.end_lineno, replacements[node.name].rstrip() + '\n'))
    seen = {x.name for x in tree.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
    missing = set(replacements) - seen
    if missing:
        raise RuntimeError(f'Phase 7 routes not found: {sorted(missing)}')
    for start, end, source in sorted(edits, reverse=True):
        lines[start:end] = [source]
    modified = ''.join(lines)
    ast.parse(modified)
    return modified


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f'Unexpected {label} source: expected one safe anchor, found {text.count(old)}')
    return text.replace(old, new, 1)


def updated_models(source: str) -> str:
    if 'class CustomerReviewImage(' in source:
        raise RuntimeError('Review image model already exists; refusing double application')
    source = replace_once(source,
        "        UniqueConstraint('listing_id', 'author_id', name='uq_customer_review_author_listing'),\n",
        "        Index('ix_customer_reviews_listing_author', 'listing_id', 'author_id'),\n",
        'Phase 7 unique review constraint')
    source += '\n\nimport sqlalchemy as _phase71_sa\n'
    source += '''\n\nclass CustomerReviewImage(Base):
    """Bounded, normalized JPEG attachment; never served unless review is published."""
    __tablename__ = 'customer_review_images'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('customer_reviews.id', ondelete='CASCADE'), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    jpeg_data: Mapped[bytes] = mapped_column(_phase71_sa.LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (
        Index('ix_customer_review_images_review', 'review_id'),
        UniqueConstraint('review_id', 'position', name='uq_customer_review_image_position'),
        CheckConstraint('position >= 0 AND position <= 4', name='ck_customer_review_image_position'),
    )
'''
    ast.parse(source)
    return source


def updated_routes(source: str) -> str:
    if '_save_review(' in source:
        raise RuntimeError('Phase 7.1 routes appear already installed')
    source = replace_ast_nodes(source, REPLACEMENTS)
    source = replace_once(source,
        'from fastapi import APIRouter, Depends, HTTPException, Query',
        'from fastapi import APIRouter, Depends, HTTPException, Query, Response',
        'fastapi imports')
    source = replace_once(source,
        'AuditEvent, CustomerReview, CustomerReviewReply, CustomerReviewReport,',
        'AuditEvent, CustomerReview, CustomerReviewReply, CustomerReviewReport, CustomerReviewImage,',
        'review model import')
    helper = (ROOT / 'tools' / 'routes_helpers.py.txt').read_text(encoding='utf-8')
    source += '\n' + helper
    ast.parse(source)
    return source


def updated_api(source: str) -> str:
    source = replace_once(source,
      'id:string; rating:number; title:string; body:string; author_label:string;',
      'id:string; rating:number; title:string; body:string; author_label:string; images:string[];',
      'public review type')
    source = replace_once(source,
      "state:'pending'|'published'|'changes_requested'|'hidden';moderation_note:string|null",
      "state:'pending'|'published'|'changes_requested'|'hidden';moderation_note:string|null;images:string[]",
      'my review type')
    source = replace_once(source,
      'export type ReviewWrite = {rating:number;title:string;body:string}',
      'export type ReviewWrite = {rating:number;title:string;body:string;images?:string[]}',
      'review input type')
    source = replace_once(source,
      'request<CustomerReviewSummary>(`/reviews/listings/${encodeURIComponent(slug)}?offset=${offset}`)',
      'request<CustomerReviewSummary>(`/reviews/listings/${encodeURIComponent(slug)}?offset=${offset}&limit=5`)',
      'five-review pagination')
    if 'export const myCustomerReviews=' in source:
        raise RuntimeError('Duplicate new review API')
    source += '''\n\n// Phase 7.1: multiple reviews, photo gallery and editing one specific review.
export const myCustomerReviews=(slug:string,token:string)=>
  request<{reviews:MyCustomerReview[];review:MyCustomerReview|null;remaining:number}>(
    `/reviews/listings/${encodeURIComponent(slug)}/mine`,{},token)
export const editCustomerReview=(id:string,body:ReviewWrite,token:string)=>
  request<{review:MyCustomerReview;message:string}>(`/reviews/${encodeURIComponent(id)}`,
    {method:'PATCH',body:JSON.stringify(body)},token)
'''
    return source


def patch_tests(source: str) -> str:
    # Old tests enforce the superseded "one review, always pending" behavior.
    # Retain the useful tests by replacing obsolete expectations, and provide
    # new Phase 7.1 test cases in a separate file.
    source = source.replace("    assert 'uq_customer_review_author_listing' in names\n", "    assert 'uq_customer_review_author_listing' not in names\n")
    source = source.replace("    assert set(response)=={'id','rating','title','body','author_label','visit_verified','created_at','response'}",
                            "    assert set(response)=={'id','rating','title','body','author_label','visit_verified','created_at','images','response'}")
    replacements = {
        'test_private_submission_overrides_published_state_and_withholds_published_reply':
        """def test_editing_someone_elses_review_is_denied():
    writer=SimpleNamespace(id=uuid4())
    previous=SimpleNamespace(id=uuid4(),author_id=uuid4())
    db=Mock();db.scalar.return_value=previous
    with pytest.raises(HTTPException) as err:
        feedback.edit_feedback(previous.id,feedback.ReviewWrite(
            rating=4,title='A title',body='A review long enough to be useful and truthful.'),writer,db)
    assert err.value.status_code==404
    db.commit.assert_not_called()
""",
        'test_hidden_review_cannot_be_resubmitted':
        """def test_five_review_cap_refuses_sixth_submission(monkeypatch):
    author=SimpleNamespace(id=uuid4(),profile_completed_at=datetime.now(timezone.utc))
    listing=SimpleNamespace(id=uuid4(),organization_id=uuid4())
    db=Mock();db.scalar.side_effect=[author.id,5]
    monkeypatch.setattr(feedback,'_public_listing',lambda _db,_slug:listing)
    monkeypatch.setattr(feedback,'_eligible_author',lambda *_:None)
    with pytest.raises(HTTPException) as err:
        feedback.submit_feedback('hotel',feedback.ReviewWrite(
            rating=4,title='Detailed title',body='A very detailed updated account of this experience.'),author,db)
    assert err.value.status_code==409
    db.commit.assert_not_called()
""",
        'test_published_review_query_only_counts_public_listing_independently_moderated':
        """def test_published_review_query_is_limited_and_counted(monkeypatch):
    listing=SimpleNamespace(id=uuid4())
    monkeypatch.setattr(feedback,'_public_listing',lambda _db,slug:listing)
    db=Mock();db.scalar.side_effect=[3,4.333333]
    db.scalars.return_value.all.return_value=[]
    output=feedback.listing_feedback('sample',5,0,db)
    assert output['count']==3
    assert output['average_rating']==4.33
    compiled=str(db.scalar.call_args_list[0].args[0].compile(dialect=dialect()))
    assert 'customer_reviews.state =' in compiled
""",
    }
    updated = replace_ast_nodes(source, replacements)
    ast.parse(updated)
    return updated


def preflight(repo: Path) -> None:
    needed = [
      'apps/api/tourismo/reviews/routes.py',
      'apps/api/tourismo/core/models.py',
      'apps/api/migrations/versions/0016_customer_reviews.py',
      'apps/web/src/features/CustomerReviews.tsx',
      'apps/web/src/lib/api.ts',
    ]
    for f in needed:
        if not (repo / f).is_file():
            raise RuntimeError(f'Missing Phase 7 prerequisite: {f}')
    if (repo/'apps/api/migrations/versions/0017_service_enquiries.py').exists():
        raise RuntimeError('Phase 8 already present: this Phase 7.1 change needs an Alembic rebase. Do not run.')
    if (repo/'apps/api/migrations/versions/0017_review_media_autopublish.py').exists():
        raise RuntimeError('Phase 7.1 already appears installed. Stop to avoid overwriting changes.')
    current_ui = (repo/'apps/web/src/features/CustomerReviews.tsx').read_text(encoding='utf-8')
    if 'One review per account and service.' not in current_ui or 'CustomerReviews' not in current_ui:
        raise RuntimeError('CustomerReviews component differs from Phase 7 release: cannot safely replace custom code')
    requirements = repo / 'apps/api/requirements.txt'
    if not requirements.exists():
        raise RuntimeError('Could not locate apps/api/requirements.txt to add Pillow safely; installation aborted')


def build_changes(repo: Path) -> dict[Path,str]:
    preflight(repo)
    output: dict[Path,str] = {}
    for relative, transform in [
      ('apps/api/tourismo/core/models.py', updated_models),
      ('apps/api/tourismo/reviews/routes.py', updated_routes),
      ('apps/web/src/lib/api.ts', updated_api),
    ]:
        output[repo/relative] = transform((repo/relative).read_text(encoding='utf-8'))
    reqfile = repo/'apps/api/requirements.txt'
    req=reqfile.read_text(encoding='utf-8')
    if not any(line.strip().lower().startswith('pillow') for line in req.splitlines()):
        output[reqfile] = req.rstrip()+'\nPillow>=10.4,<13\n'
    original_tests = repo/'apps/api/tests/test_phase7_customer_reviews.py'
    if original_tests.is_file():
        output[original_tests]=patch_tests(original_tests.read_text(encoding='utf-8'))
    for relative in [
       'apps/api/migrations/versions/0017_review_media_autopublish.py',
       'apps/api/tourismo/reviews/safety.py',
       'apps/api/tests/test_phase71_review_policy.py',
       'apps/web/src/features/CustomerReviews.tsx',
    ]:
        output[repo/relative] = (SRC/relative).read_text(encoding='utf-8')
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check',action='store_true',help='validate source anchors without writing')
    group.add_argument('--apply',action='store_true',help='backup originals and write new source files')
    group.add_argument('--export-patch',metavar='PATH',help='generate an exact Git patch against this local repository; write no source files')
    args=parser.parse_args()
    changes = build_changes(REPO)
    print(f'Phase 7.1 preflight OK: {len(changes)} planned files')
    for path in changes:
        print(' -', path.relative_to(REPO))
    if args.check:
        print('DRY-RUN ONLY: no files changed')
        return
    if args.export_patch:
        patch_lines = []
        for path, new_source in changes.items():
            relative = path.relative_to(REPO).as_posix()
            existed = path.exists()
            old_source = path.read_text(encoding='utf-8') if existed else ''
            if old_source == new_source:
                continue
            old_lines = old_source.splitlines(keepends=True)
            new_lines = new_source.splitlines(keepends=True)
            patch_lines.append(f'diff --git a/{relative} b/{relative}\n')
            if not existed:
                patch_lines.append('new file mode 100644\n')
            patch_lines.extend(difflib.unified_diff(
                old_lines, new_lines, fromfile=f'a/{relative}' if existed else '/dev/null',
                tofile=f'b/{relative}', n=3,
            ))
        export = Path(args.export_patch).expanduser().resolve()
        export.parent.mkdir(parents=True, exist_ok=True)
        export.write_text(''.join(patch_lines), encoding='utf-8', newline='\n')
        print(f'Generated an exact changes-only Git patch: {export}')
        print('NEXT: git apply --check <patch>, then git apply <patch>')
        return
    backup_root=REPO/'.phase7_1_backup'/datetime.now().strftime('%Y%m%d-%H%M%S')
    for path in changes:
        relative=path.relative_to(REPO)
        if path.exists():
            copy=backup_root/relative
            copy.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,copy)
    for path,source in changes.items():
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(source,encoding='utf-8',newline='\n')
    print('Source update written. Backups:',backup_root)
    print('IMPORTANT: do NOT run database migration until DB backup is verified.')


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print('STOP: '+str(exc),file=sys.stderr)
        raise SystemExit(2)
